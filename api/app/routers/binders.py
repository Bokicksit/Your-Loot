"""Making, reading and filling binders."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import binders as engine
from app.auth import current_user
from app.binder_view import render
from app.db import get_db
from app.limits import binder_limit, limited
from app.models import Binder, BinderSlot, CardAttrs, CollectionItem, Module, Owned, User

router = APIRouter(prefix="/api/binders", tags=["binders"])


# "#rrggbb". Anchored, because a pattern that is not will happily accept a
# colour with an essay after it.
HEX = "^#[0-9a-fA-F]{6}$"


class Shape(BaseModel):
    """How the binder is drawn: pockets across, pockets down, and whether it
    is read as a spread of two facing pages."""

    rows: int = Field(default=3, ge=1, le=engine.MAX_SIDE)
    cols: int = Field(default=3, ge=1, le=engine.MAX_SIDE)
    double_page: bool = False
    color: str | None = Field(default=None, pattern=HEX)
    # whether Japanese cards belong in it; off is the answer for a binder
    # that was English before there were any
    allow_ja: bool = False


class BinderCreate(Shape):
    name: str = Field(min_length=1, max_length=60)
    kind: str = Field(pattern="^(set|custom)$")  # the dex one already exists
    set_code: str | None = None
    # set binders only: a slot per printing rather than per card
    master: bool = False
    # custom binders only: start it as an empty binder of this many pages,
    # ready to be filled in place. Zero keeps the old behaviour — a binder
    # with nothing in it that grows as you add cards.
    pages: int = Field(default=0, ge=0, le=engine.MAX_PAGES)


class BinderEdit(BaseModel):
    """All optional: the cover can be set without retyping the name, and
    cleared by sending an empty string rather than by omitting it, which means
    "leave it alone". The same is true of the colour."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    image_url: str | None = Field(default=None, max_length=500)
    # set binders only: switch between a slot per card and a slot per printing
    master: bool | None = None

    # Shape, all of it safe to change whenever: no slot moves because the page
    # got wider, only where the breaks between pages fall.
    rows: int | None = Field(default=None, ge=1, le=engine.MAX_SIDE)
    cols: int | None = Field(default=None, ge=1, le=engine.MAX_SIDE)
    double_page: bool | None = None
    allow_ja: bool | None = None
    # whether this one is on the public profile, where this install has them
    on_profile: bool | None = None
    # "" clears it back to the shelf's own colour
    color: str | None = Field(default=None, pattern=f"{HEX}|^$")

    # custom binders only. Growing appends blank pages; shrinking takes empty
    # ones off the end and stops at the first that holds a card, because "make
    # it four pages" is never a request to throw two pages of cards away.
    pages: int | None = Field(default=None, ge=0, le=engine.MAX_PAGES)


class SlotFill(BaseModel):
    owned_id: int | None = None  # null empties the slot
    item_id: int | None = None
    # which printing's slot, on a master binder — "" is the only slot the
    # other kinds have
    variant: str = ""


class HappyUpdate(BaseModel):
    happy: bool


class AddCards(BaseModel):
    """Cards for a custom binder, in the order given."""
    owned_ids: list[int] = Field(min_length=1, max_length=500)


class Reorder(BaseModel):
    slot_ids: list[int]


def _mine(db: Session, binder_id: int, user: User) -> Binder:
    b = db.get(Binder, binder_id)
    # "not found" rather than "not yours": whether somebody else has a binder
    # is none of your business
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "binder not found")
    return b


# Said the same way wherever it is said, because somebody hitting it in the
# Pokédex and again in a binder of their own should not have to work out
# whether they are two different rules.
_NOT_HERE = (
    "This binder is English. Turn on Japanese cards in its settings to file "
    "one here."
)


def _resize(db: Session, b: Binder, pages: int) -> None:
    """Make a custom binder this many pages long.

    Growing adds blank pockets on the end. Shrinking takes them off the end
    and stops the moment it meets one with a card in it, because "make it four
    pages" is a statement about the size of the binder and never a request to
    throw two pages of cards away. Saying so is better than a confirm dialog:
    the binder is still the size it was, and nothing was lost while you
    decided.
    """
    slots = db.scalars(
        select(BinderSlot)
        .where(BinderSlot.binder_id == b.id)
        .order_by(BinderSlot.position, BinderSlot.id)
    ).all()
    want = pages * engine.per_page(b)

    if want > len(slots):
        if want > engine.MAX_BLANKS:
            raise HTTPException(
                422,
                f"that is {want} pockets — {engine.MAX_BLANKS} is as many as one "
                "binder can hold",
            )
        last = slots[-1].position if slots else 0
        for n in range(1, want - len(slots) + 1):
            db.add(BinderSlot(binder_id=b.id, position=(last or 0) + n))
        return

    doomed = slots[want:]
    held = [s for s in doomed if s.owned_id or s.item_id]
    if held:
        raise HTTPException(
            409,
            f"{len(held)} card{'s' if len(held) > 1 else ''} would have to come "
            f"out to make it {pages} page{'s' if pages != 1 else ''}. Take them "
            "out first, or leave it the size it is.",
        )
    for s in doomed:
        db.delete(s)


def _my_copy(db: Session, owned_id: int, user: User) -> Owned:
    o = db.get(Owned, owned_id)
    if o is None or o.user_id != user.id:
        raise HTTPException(404, "copy not found")
    return o


@router.get("")
def list_binders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Every binder, with enough to draw a shelf of them.

    The counts are done in SQL rather than by rendering each binder, because
    rendering a set binder walks its whole set and a shelf of ten would be ten
    of those for a number on a card.
    """
    rows = db.scalars(
        select(Binder).where(Binder.user_id == user.id).order_by(
            # placed binders first, in the order they were placed; the rest
            # fall in behind by kind and name, which is where a new one lands
            Binder.position.is_(None), Binder.position, Binder.kind, Binder.name
        )
    ).all()

    filled = dict(
        db.execute(
            select(BinderSlot.binder_id, func.count())
            .where(BinderSlot.owned_id.is_not(None))
            .group_by(BinderSlot.binder_id)
        ).all()
    )
    # A set binder counts what you own of the set, not what you filed. A
    # master one counts printings, and the arithmetic for that lives in the
    # renderer — the shelf saying "0 of 25" while the binder itself shows 42
    # slots is the kind of disagreement nobody can explain later. Sets are a
    # few hundred rows and a shelf holds a handful of binders, so rendering
    # them is cheaper than keeping a second copy of the rule.
    set_totals, set_owned = {}, {}
    for b in (x for x in rows if x.kind == engine.SET):
        if b.master:
            counted = render(db, b, user.id)["binder"]
            set_totals[b.id], set_owned[b.id] = counted["total"], counted["filled"]
            continue
        set_totals[b.id] = db.scalar(
            select(func.count()).select_from(CardAttrs)
            .where(CardAttrs.set_code == b.set_code)
        ) or 0
        set_owned[b.id] = db.scalar(
            select(func.count(func.distinct(CollectionItem.id)))
            .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
            .join(Owned, Owned.item_id == CollectionItem.id)
            .where(CardAttrs.set_code == b.set_code, Owned.user_id == user.id)
        ) or 0

    out = []
    for b in rows:
        if b.kind == engine.DEX:
            total, have = 1025, filled.get(b.id, 0)
        elif b.kind == engine.SET:
            total, have = set_totals.get(b.id, 0), set_owned.get(b.id, 0)
        else:
            total = db.scalar(
                select(func.count()).select_from(BinderSlot)
                .where(BinderSlot.binder_id == b.id)
            ) or 0
            have = filled.get(b.id, 0)
        out.append({
            "id": b.id, "name": b.name, "kind": b.kind,
            "set_code": b.set_code, "master": b.master, "image_url": b.image_url,
            "color": b.color, "position": b.position,
            "rows": b.rows, "cols": b.cols, "double_page": b.double_page,
            "allow_ja": b.allow_ja,
            "on_profile": b.on_profile,
            "pages": engine.page_count(b, total),
            "total": total, "filled": have, "missing": max(total - have, 0),
        })
    return {"binders": out}


@router.post("", status_code=201)
def create_binder(
    body: BinderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    # The Pokédex binder is not counted: it is the one everybody gets, capped
    # by how far up it goes rather than by existing at all. Everything else —
    # a custom shelf or a master set — comes out of the same single allowance,
    # so somebody free chooses which one they want rather than being told.
    if limited(user) and binder_limit() and body.kind != engine.DEX:
        held = db.scalar(
            select(func.count()).select_from(Binder).where(
                Binder.user_id == user.id, Binder.kind != engine.DEX
            )
        ) or 0
        if held >= binder_limit():
            raise HTTPException(
                402,
                f"The free plan keeps {binder_limit()} binder besides the Pokédex. "
                "Nothing you have made is going anywhere — Supporter lifts the "
                "limit, and self-hosting has none at all.",
            )

    if body.kind == engine.SET:
        if not body.set_code:
            raise HTTPException(422, "a set binder needs a set")
        known = db.scalar(
            select(func.count()).select_from(CardAttrs)
            .where(CardAttrs.set_code == body.set_code)
        )
        if not known:
            raise HTTPException(404, f"no cards in the catalogue for set {body.set_code!r}")
        # The picker only offers English sets; this is the same rule for
        # anybody reaching the endpoint directly, so the two cannot disagree.
        english = db.scalar(
            select(func.count()).select_from(CardAttrs)
            .where(CardAttrs.set_code == body.set_code, CardAttrs.language == "en")
        )
        if not english:
            raise HTTPException(
                409,
                "Japanese sets don't get set binders. They go in your "
                "collection, the Pokédex, or a binder of your own.",
            )
        clash = db.scalar(
            select(Binder).where(
                Binder.user_id == user.id, Binder.kind == engine.SET,
                Binder.set_code == body.set_code,
                Binder.master.is_(bool(body.master)),
            )
        )
        if clash:
            raise HTTPException(409, f"you already have a binder for that set: {clash.name!r}")

    b = Binder(
        user_id=user.id, name=body.name.strip(), kind=body.kind,
        set_code=body.set_code if body.kind == engine.SET else None,
        master=bool(body.master) and body.kind == engine.SET,
        rows=body.rows, cols=body.cols,
        double_page=body.double_page, color=body.color,
        allow_ja=body.allow_ja,
    )
    db.add(b)
    db.commit()

    # An empty binder of a stated size, ready to be filled in place. Only a
    # custom binder can have one: the other two get their pages from a
    # universe the app already knows, and padding those with blanks would
    # invent slots the set does not have.
    if b.kind == engine.CUSTOM and body.pages:
        wanted = body.pages * engine.per_page(b)
        if wanted > engine.MAX_BLANKS:
            raise HTTPException(
                422,
                f"that is {wanted} pockets — {engine.MAX_BLANKS} is as many as "
                "one binder can be made with at once",
            )
        for n in range(1, wanted + 1):
            db.add(BinderSlot(binder_id=b.id, position=n))
        db.commit()

    # A master binder needs to know which printings each card exists in, and
    # only TCGdex knows. Asked once per set, here, so the binder is right the
    # first time it is opened rather than filling in later.
    learned = None
    if b.master and not engine.printings_known(db, b.set_code):
        name = db.scalar(
            select(CardAttrs.set_name).where(CardAttrs.set_code == b.set_code).limit(1)
        )
        try:
            learned = engine.learn_printings(db, b.set_code, name)
        except Exception as exc:
            # The binder is made and usable — every card falls back to one
            # slot until this succeeds. Losing the binder over a third party
            # being slow would be the worse answer.
            learned = {"matched": False, "error": str(exc)[:200]}

    return {"id": b.id, "name": b.name, "kind": b.kind, "set_code": b.set_code,
            "image_url": b.image_url, "color": b.color, "master": b.master,
            "rows": b.rows, "cols": b.cols, "double_page": b.double_page,
            "allow_ja": b.allow_ja,
            "on_profile": b.on_profile,
            "printings": learned}


@router.get("/{binder_id}")
def read_binder(
    binder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return render(db, _mine(db, binder_id, user), user.id)


@router.patch("/{binder_id}")
def edit_binder(
    binder_id: int,
    body: BinderEdit,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    b = _mine(db, binder_id, user)
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"]:
        b.name = fields["name"].strip()
    if "image_url" in fields:
        b.image_url = (fields["image_url"] or "").strip() or None
    if "color" in fields:
        b.color = (fields["color"] or "").strip().lower() or None
    for side in ("rows", "cols"):
        if fields.get(side) is not None:
            setattr(b, side, fields[side])
    if fields.get("double_page") is not None:
        b.double_page = bool(fields["double_page"])
    if fields.get("allow_ja") is not None:
        b.allow_ja = bool(fields["allow_ja"])
    if fields.get("on_profile") is not None:
        b.on_profile = bool(fields["on_profile"])

    # Pages last, so it is measured against the shape you just set rather than
    # the one you are replacing — "three by three, four pages" in one press
    # should mean thirty-six pockets, not four pages of whatever it was.
    if fields.get("pages") is not None:
        if b.kind != engine.CUSTOM:
            raise HTTPException(409, "only a custom binder is filled by hand")
        _resize(db, b, fields["pages"])

    learned = None
    if "master" in fields and fields["master"] is not None:
        want = bool(fields["master"])
        if b.kind != engine.SET:
            raise HTTPException(409, "only a set binder has printings to split")
        if want != b.master:
            clash = db.scalar(
                select(Binder).where(
                    Binder.user_id == user.id, Binder.kind == engine.SET,
                    Binder.set_code == b.set_code, Binder.master.is_(want),
                    Binder.id != b.id,
                )
            )
            if clash:
                raise HTTPException(
                    409, f"you already have that binder in this mode: {clash.name!r}"
                )
            b.master = want
            # Slots survive the switch. A keeper flag is about the card in the
            # slot, and the plain slot of a master binder is the same slot the
            # simple one had — going back and forth must not cost you what you
            # marked.
            if want and not engine.printings_known(db, b.set_code):
                name = db.scalar(
                    select(CardAttrs.set_name)
                    .where(CardAttrs.set_code == b.set_code).limit(1)
                )
                try:
                    learned = engine.learn_printings(db, b.set_code, name)
                except Exception as exc:
                    learned = {"matched": False, "error": str(exc)[:200]}

    db.commit()
    return {"id": b.id, "name": b.name, "image_url": b.image_url,
            "master": b.master, "printings": learned}


@router.delete("/{binder_id}", status_code=204)
def delete_binder(
    binder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Throws away the binder, not the cards.

    Slots go with it — they are how the binder was arranged, and the
    arrangement is the thing being deleted. Every card is still owned.
    """
    b = _mine(db, binder_id, user)
    if b.kind == engine.DEX:
        raise HTTPException(409, "the Pokédex cannot be deleted, only emptied")
    db.delete(b)
    db.commit()


@router.put("/{binder_id}/slots/{key}")
def fill_slot(
    binder_id: int,
    key: str,
    body: SlotFill,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Put a copy in a slot, or empty it."""
    b = _mine(db, binder_id, user)
    if body.owned_id is None:
        s = engine.slot(db, b, key, body.variant)
        if s is not None and s.owned_id is not None:
            engine.unfile(db, s.owned_id, b.id)
        db.commit()
        return render(db, b, user.id)

    copy = _my_copy(db, body.owned_id, user)
    if not engine.may_hold(b, copy.item):
        raise HTTPException(409, _NOT_HERE)
    engine.file_copy(
        db, b, key, copy.id,
        item_id=body.item_id or copy.item_id, variant=body.variant,
    )
    db.commit()
    return render(db, b, user.id)


@router.put("/{binder_id}/slots/{key}/happy")
def slot_happy(
    binder_id: int,
    key: str,
    body: HappyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    b = _mine(db, binder_id, user)
    # "The one" is a Pokédex idea: it settles which of the several cards that
    # could fill a slot actually does. A set slot names one exact card and a
    # custom slot holds the one you chose, so neither has anything to settle.
    if b.kind != engine.DEX:
        raise HTTPException(409, "only the Pokédex has cards to choose between")
    engine.set_happy(db, b, key, body.happy)
    db.commit()
    return {"key": key, "happy": body.happy}


@router.post("/{binder_id}/cards")
def add_cards(
    binder_id: int,
    body: AddCards,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Put copies into a custom binder: the empty pockets first, then the end.

    Filling the gaps before growing is the whole point of being able to make a
    binder blank. A binder set up as ten empty pages is a binder somebody
    means to fill in place, and appending to the end would file the first card
    they added onto page eleven, behind all the empties they just asked for.

    It also does the right thing for a binder with no gaps, where "first empty
    pocket, then the end" is exactly the old behaviour of adding to the end.
    """
    b = _mine(db, binder_id, user)
    if b.kind != engine.CUSTOM:
        raise HTTPException(409, "only a custom binder is filled by hand")

    empty = db.scalars(
        select(BinderSlot)
        .where(
            BinderSlot.binder_id == b.id,
            BinderSlot.owned_id.is_(None),
            BinderSlot.item_id.is_(None),
        )
        .order_by(BinderSlot.position, BinderSlot.id)
    ).all()
    last = db.scalar(
        select(func.max(BinderSlot.position)).where(BinderSlot.binder_id == b.id)
    ) or 0

    grown = 0
    for owned_id in body.owned_ids:
        copy = _my_copy(db, owned_id, user)
        if not engine.may_hold(b, copy.item):
            raise HTTPException(409, _NOT_HERE)
        if empty:
            s = empty.pop(0)
            s.item_id = copy.item_id
        else:
            grown += 1
            s = BinderSlot(binder_id=b.id, position=last + grown, item_id=copy.item_id)
            db.add(s)
        s.owned = copy
    db.commit()
    return render(db, b, user.id)


@router.post("/{binder_id}/slots/blank")
def add_blank(
    binder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """A page with nothing on it, added at the end.

    A real binder is not always full front to back — a gap separates one run
    from the next, or holds a space for the card that has not turned up yet.
    The row itself is the same one a sold card leaves behind, so nothing here
    is new except being able to ask for it on purpose.

    Added at the end and moved with Arrange, rather than inserted at an index:
    the two-tap move already exists and knows how to slide everything else
    along, and a second way of saying where a page goes is a second thing that
    can disagree with the first.
    """
    b = _mine(db, binder_id, user)
    if b.kind != engine.CUSTOM:
        raise HTTPException(409, "only a custom binder is filled by hand")

    last = db.scalar(
        select(func.max(BinderSlot.position)).where(BinderSlot.binder_id == b.id)
    ) or 0
    db.add(BinderSlot(binder_id=b.id, position=last + 1))
    db.commit()
    return render(db, b, user.id)


@router.delete("/{binder_id}/slots/{slot_id}", status_code=204)
def remove_slot(
    binder_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Take a page out of a custom binder."""
    b = _mine(db, binder_id, user)
    s = db.get(BinderSlot, slot_id)
    if s is None or s.binder_id != b.id:
        raise HTTPException(404, "slot not found")
    s.owned = None
    db.delete(s)
    db.commit()


@router.delete("/{binder_id}/cards/{owned_id}", status_code=204)
def remove_card(
    binder_id: int,
    owned_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Take a copy out, named by the copy rather than by its slot.

    The card list knows which binders a copy is in but not which slot of each,
    and asking it to find out first would be a round trip to learn something
    the server already knows.
    """
    b = _mine(db, binder_id, user)
    _my_copy(db, owned_id, user)
    if b.kind == engine.CUSTOM:
        # The page stays, empty. It used to be deleted, on the reasoning that a
        # custom slot only exists because you put something there — true then,
        # and no longer, now that a blank page is something you can add on
        # purpose. Keeping it means taking one card out does not shuffle every
        # card after it up a place, which is not what pulling a card out of a
        # binder does. Removing the page itself is its own button.
        for s in db.scalars(
            select(BinderSlot).where(
                BinderSlot.binder_id == b.id, BinderSlot.owned_id == owned_id
            )
        ).all():
            s.owned = None
            s.item_id = None
    else:
        engine.unfile(db, owned_id, b.id)
    db.commit()


@router.put("/{binder_id}/order")
def reorder(
    binder_id: int,
    body: Reorder,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """The order is the binder, so this is a first-class operation rather than
    a field on something else."""
    b = _mine(db, binder_id, user)
    if b.kind != engine.CUSTOM:
        raise HTTPException(409, "only a custom binder has an order of its own")
    mine = {
        s.id: s
        for s in db.scalars(select(BinderSlot).where(BinderSlot.binder_id == b.id)).all()
    }
    unknown = [i for i in body.slot_ids if i not in mine]
    if unknown:
        raise HTTPException(404, f"not slots in this binder: {unknown}")
    for n, slot_id in enumerate(body.slot_ids, start=1):
        mine[slot_id].position = n
    # anything the caller didn't mention keeps its order, after the rest
    rest = [s for i, s in mine.items() if i not in set(body.slot_ids)]
    for n, s in enumerate(sorted(rest, key=lambda x: (x.position or 0, x.id)), start=1):
        s.position = len(body.slot_ids) + n
    db.commit()
    return render(db, b, user.id)


@router.post("/{binder_id}/printings")
def refresh_printings(
    binder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Ask TCGdex again which printings this set has.

    For the set it could not match the first time, or one that has grown since
    — a set gains secret rares after release more often than you would think.
    """
    b = _mine(db, binder_id, user)
    if b.kind != engine.SET:
        raise HTTPException(409, "only a set binder has printings to look up")
    name = db.scalar(
        select(CardAttrs.set_name).where(CardAttrs.set_code == b.set_code).limit(1)
    )
    return engine.learn_printings(db, b.set_code, name)


class ShelfOrder(BaseModel):
    binder_ids: list[int]


@router.put("/order")
def reorder_shelf(
    body: ShelfOrder,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Arrange the shelf.

    Kind and then name is a reasonable order and nobody's actual one — a real
    shelf is arranged by what you reach for. Anything the caller does not
    mention keeps its place behind the ones it does.
    """
    mine = {
        b.id: b
        for b in db.scalars(select(Binder).where(Binder.user_id == user.id)).all()
    }
    unknown = [i for i in body.binder_ids if i not in mine]
    if unknown:
        raise HTTPException(404, f"not your binders: {unknown}")
    for n, binder_id in enumerate(body.binder_ids, start=1):
        mine[binder_id].position = n
    rest = [b for i, b in mine.items() if i not in set(body.binder_ids)]
    for n, b in enumerate(sorted(rest, key=lambda x: (x.position or 0, x.id)), start=1):
        b.position = len(body.binder_ids) + n
    db.commit()
    return list_binders(db=db, user=user)


@router.get("/sets/available")
def sets_available(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Sets you could make a binder of, newest first, with how many of each
    you already own — which is the number that decides whether it is worth
    making one."""
    have = dict(
        db.execute(
            select(CardAttrs.set_code, func.count(func.distinct(CollectionItem.id)))
            .join(CollectionItem, CollectionItem.id == CardAttrs.item_id)
            .join(Owned, Owned.item_id == CollectionItem.id)
            .where(Owned.user_id == user.id)
            .group_by(CardAttrs.set_code)
        ).all()
    )
    # one binder per set *per mode*, so the picker has to know which of the
    # two you already have rather than just that you have one
    taken, taken_master = set(), set()
    for code, is_master in db.execute(
        select(Binder.set_code, Binder.master).where(
            Binder.user_id == user.id, Binder.kind == engine.SET
        )
    ).all():
        (taken_master if is_master else taken).add(code)
    rows = db.execute(
        select(
            CardAttrs.set_code, CardAttrs.set_name, CardAttrs.set_abbr,
            CardAttrs.set_year, func.count(), func.max(CardAttrs.set_total),
        )
        # English sets only. A set binder is a set with a slot per card, and
        # the Japanese sets are not offered as binders — they would add a
        # hundred and twenty-four entries to this list, each of them a binder
        # whose master mode would need printings nobody publishes for them.
        # Japanese cards go in the collection, the Pokédex and binders of
        # your own, which is where somebody who collects them wants them.
        .where(
            CollectionItem.module == Module.cards.value,
            CardAttrs.language == "en",
        )
        .join(CollectionItem, CollectionItem.id == CardAttrs.item_id)
        .group_by(
            CardAttrs.set_code, CardAttrs.set_name, CardAttrs.set_abbr, CardAttrs.set_year
        )
        .order_by(CardAttrs.set_year.desc().nulls_last(), CardAttrs.set_name)
    ).all()
    return {
        "sets": [
            {
                "code": code, "name": name, "abbr": abbr, "year": year,
                "cards": cards, "printed": printed,
                "owned": have.get(code, 0),
                "has_binder": code in taken, "has_master": code in taken_master,
            }
            for code, name, abbr, year, cards, printed in rows
        ]
    }
