"""One person's view of a shared catalogue.

The catalogue is common ground and stays that way — a Charizard is the same
card whoever holds it. Everything hanging off it is not: how worn your copy
is, what you paid, the cert number on your slab, whether you're still hunting
one.

Every router needs the same four answers, so they live here rather than being
written out thirteen times. Thirteen hand-written filters is thirteen chances
to forget one, and a forgotten one is invisible from the inside — the app
looks right until somebody else's collection turns up in yours.
"""

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.models import CollectionItem, Owned, Wanted


def visible(user_id: int):
    """Which catalogue rows this person may see.

    Everything, minus the rows that belong to somebody else. Almost every row
    is shared and answers this trivially; the exceptions are entries created
    by importing a collection, which had no external id to match against and
    so were nobody's fact but the importer's.

    A condition rather than a filtered query, because the eight collections
    each build their own query and this has to go into all of them. Every one
    of them is checked by test_privacy — a filter that is merely usually
    applied is not a filter.
    """
    return or_(
        CollectionItem.private_to.is_(None),
        CollectionItem.private_to == user_id,
    )


def my_copies(item, user_id: int) -> list:
    """Only this person's copies of an item.

    Filtered in Python rather than by the query on purpose: the relationship
    is already loaded, an item has a handful of copies at most, and doing it
    here means one rule covers every module instead of eight loader options
    that have to agree.
    """
    return [o for o in item.owned if o.user_id == user_id]


def my_want(item, user_id: int):
    """This person's wanted entry, or None.

    `item.wanted` is a list now — it stopped being one-per-item the moment
    two people could want the same thing — but callers still want the single
    answer, and the response shape stays what it always was.
    """
    return next((w for w in item.wanted if w.user_id == user_id), None)


def owns(user_id: int, item_col):
    """EXISTS: this person has a copy. For filtering a collection list."""
    return (
        select(Owned.id)
        .where(Owned.item_id == item_col, Owned.user_id == user_id)
        .exists()
    )


def wants(user_id: int, item_col):
    """EXISTS: this person is hunting it."""
    return (
        select(Wanted.id)
        .where(Wanted.item_id == item_col, Wanted.user_id == user_id)
        .exists()
    )


def _holds(db, item_id: int, user_id: int, *, someone_else: bool = False) -> bool:
    """A copy or a want — the stake that makes a shared row partly yours.

    With `someone_else`, the same question about everybody but you: the
    reason a delete has to refuse, since the cascade would take their copies
    down with the row.
    """
    own = Owned.user_id != user_id if someone_else else Owned.user_id == user_id
    want = Wanted.user_id != user_id if someone_else else Wanted.user_id == user_id
    return bool(
        db.scalar(select(Owned.id).where(Owned.item_id == item_id, own).limit(1))
        or db.scalar(select(Wanted.id).where(Wanted.item_id == item_id, want).limit(1))
    )


def guard_entry_write(db, item, user, *, deleting: bool = False) -> None:
    """The gate in front of editing or deleting a catalogue row.

    Reads were always scoped — visible() and on_my_shelf() in every list —
    but the write endpoints took any item id, which on a multi-user install
    let one account rewrite or cascade-delete another's shelf. This is the
    same rule for all eight modules, in one place, for the same reason the
    read filters live here.

    * A row somebody else imported privately does not exist for you: 404,
      the answer visible() already gives, and saying "forbidden" instead
      would confirm there is something to forbid.
    * Touching a shared row needs a stake — your copy or your want. A row
      nobody at all holds is an orphan (a half-finished add, an import
      remnant) and anyone may fix or clear it; nothing of anybody's hangs
      off it.
    * Deleting refuses while somebody else still holds the row (409): the
      FK cascade would take their copies and binder slots with it. Removing
      your own copies is what "I sold it" means, and that path checks
      ownership already.
    * Admins pass. The operator cleans up after moderation, and the owner
      of a single-user install is the admin — which keeps a home server
      exactly as unrestricted as it has always been.
    """
    if user.is_admin:
        return
    if item.private_to not in (None, user.id):
        raise HTTPException(404, "not found")
    mine = _holds(db, item.id, user.id)
    theirs = _holds(db, item.id, user.id, someone_else=True)
    if not mine and theirs:
        raise HTTPException(404, "not found")
    if deleting and theirs:
        raise HTTPException(
            409, "somebody else keeps a copy of this — remove your own copies instead"
        )


def on_my_shelf(user_id: int, item_col, include_wanted: bool = False):
    """What a collection page shows: the things you own.

    This used to read "owned by anyone, OR wanted by no one", which was a
    sound way to say "not a wishlist ghost" back when there was one person
    and their absence of a wish spoke for everybody. With two people the
    second half is true of every item the *other* one owns, so the rule let
    the whole server through — which is exactly what the sweep test caught.

    A shelf is what you own. A row you have no copy of is somebody else's,
    or a catalogue entry, and neither belongs on it. `include_wanted` is the
    Wanted tab asking for the other half back.
    """
    mine = owns(user_id, item_col)
    return mine | wants(user_id, item_col) if include_wanted else mine
