"""Making, reading and filling binders."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import binders as engine
from app.auth import current_user
from app.binder_view import render
from app.db import get_db
from app.models import Binder, BinderSlot, CardAttrs, CollectionItem, Module, Owned, User

router = APIRouter(prefix="/api/binders", tags=["binders"])


class BinderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: str = Field(pattern="^(set|custom)$")  # the dex one already exists
    set_code: str | None = None


class BinderRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class SlotFill(BaseModel):
    owned_id: int | None = None  # null empties the slot
    item_id: int | None = None


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
        select(Binder).where(Binder.user_id == user.id).order_by(Binder.kind, Binder.name)
    ).all()

    filled = dict(
        db.execute(
            select(BinderSlot.binder_id, func.count())
            .where(BinderSlot.owned_id.is_not(None))
            .group_by(BinderSlot.binder_id)
        ).all()
    )
    # a set binder counts what you own of the set, not what you filed
    set_totals, set_owned = {}, {}
    for b in (x for x in rows if x.kind == engine.SET):
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
            "set_code": b.set_code, "master": b.master,
            "total": total, "filled": have, "missing": max(total - have, 0),
        })
    return {"binders": out}


@router.post("", status_code=201)
def create_binder(
    body: BinderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if body.kind == engine.SET:
        if not body.set_code:
            raise HTTPException(422, "a set binder needs a set")
        known = db.scalar(
            select(func.count()).select_from(CardAttrs)
            .where(CardAttrs.set_code == body.set_code)
        )
        if not known:
            raise HTTPException(404, f"no cards in the catalogue for set {body.set_code!r}")
        clash = db.scalar(
            select(Binder).where(
                Binder.user_id == user.id, Binder.kind == engine.SET,
                Binder.set_code == body.set_code, Binder.master.is_(False),
            )
        )
        if clash:
            raise HTTPException(409, f"you already have a binder for that set: {clash.name!r}")

    b = Binder(
        user_id=user.id, name=body.name.strip(), kind=body.kind,
        set_code=body.set_code if body.kind == engine.SET else None,
    )
    db.add(b)
    db.commit()
    return {"id": b.id, "name": b.name, "kind": b.kind, "set_code": b.set_code}


@router.get("/{binder_id}")
def read_binder(
    binder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return render(db, _mine(db, binder_id, user), user.id)


@router.patch("/{binder_id}")
def rename_binder(
    binder_id: int,
    body: BinderRename,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    b = _mine(db, binder_id, user)
    b.name = body.name.strip()
    db.commit()
    return {"id": b.id, "name": b.name}


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
        s = engine.slot(db, b, key)
        if s is not None and s.owned_id is not None:
            engine.unfile(db, s.owned_id, b.id)
        db.commit()
        return render(db, b, user.id)

    copy = _my_copy(db, body.owned_id, user)
    engine.file_copy(db, b, key, copy.id, item_id=body.item_id or copy.item_id)
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
    """Add copies to the end of a custom binder, in the order given."""
    b = _mine(db, binder_id, user)
    if b.kind != engine.CUSTOM:
        raise HTTPException(409, "only a custom binder is filled by hand")

    last = db.scalar(
        select(func.max(BinderSlot.position)).where(BinderSlot.binder_id == b.id)
    ) or 0
    for n, owned_id in enumerate(body.owned_ids, start=1):
        copy = _my_copy(db, owned_id, user)
        s = BinderSlot(binder_id=b.id, position=last + n, item_id=copy.item_id)
        s.owned = copy
        db.add(s)
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
    taken = {
        c for (c,) in db.execute(
            select(Binder.set_code).where(
                Binder.user_id == user.id, Binder.kind == engine.SET
            )
        ).all()
    }
    rows = db.execute(
        select(
            CardAttrs.set_code, CardAttrs.set_name, CardAttrs.set_abbr,
            CardAttrs.set_year, func.count(), func.max(CardAttrs.set_total),
        )
        .where(CollectionItem.module == Module.cards.value)
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
                "owned": have.get(code, 0), "has_binder": code in taken,
            }
            for code, name, abbr, year, cards, printed in rows
        ]
    }
