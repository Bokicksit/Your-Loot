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
