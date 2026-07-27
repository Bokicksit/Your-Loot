import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import CardAttrs, CollectionItem, DexSlot, Module, Owned, Wanted
from app.schemas.cards import CardListOut, CardOut

router = APIRouter(prefix="/api/cards", tags=["cards"])

MAX_DEX = 1025  # current national dex (through Scarlet & Violet)


def card_to_out(item: CollectionItem) -> CardOut:
    return CardOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        attrs=item.card_attrs,
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.cards.value)
        .options(
            joinedload(CollectionItem.card_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search", response_model=CardListOut)
def search_cards(
    db: Session = Depends(get_db),
    name: str = Query(min_length=2),
    number: str | None = None,
    set: str | None = None,
    limit: int = Query(40, le=100),
):
    """Find a physical card by name; the printed number ("91/108", which also
    matches the set size) and set name narrow it to the exact card."""
    q = _base_query().where(CollectionItem.title.ilike(f"%{name.strip()}%"))
    total = None
    if number and number.strip():
        m = re.match(r"^\s*(\w+)\s*(?:/\s*(\d+))?\s*$", number)
        num = (m.group(1) if m else number).strip()
        total = int(m.group(2)) if m and m.group(2) else None
        # numbers are strings ("4", "091", "TG12") — match ignoring leading zeros
        stripped = num.lstrip("0") or num
        q = q.where(func.ltrim(CardAttrs.card_number, "0") == stripped)
    if total:
        q = q.where(CardAttrs.set_total == total)
    if set:
        q = q.where(CardAttrs.set_name.ilike(f"%{set.strip()}%"))

    items = (
        db.scalars(q.order_by(CardAttrs.set_code, CollectionItem.title).limit(limit))
        .unique()
        .all()
    )
    return CardListOut(total=len(items), items=[card_to_out(i) for i in items])


@router.get("/facets")
def card_facets(db: Session = Depends(get_db)):
    """Sets and rarities present among OWNED cards, with counts — drives the
    collection filter dropdowns."""
    owned_exists = select(Owned.id).where(Owned.item_id == CardAttrs.item_id).exists()
    sets = [
        {"code": c, "name": n, "count": cnt}
        for c, n, cnt in db.execute(
            select(CardAttrs.set_code, CardAttrs.set_name, func.count())
            .where(owned_exists)
            .group_by(CardAttrs.set_code, CardAttrs.set_name)
            .order_by(CardAttrs.set_name)
        )
    ]
    rarities = [
        {"rarity": r, "count": cnt}
        for r, cnt in db.execute(
            select(CardAttrs.rarity, func.count())
            .where(owned_exists, CardAttrs.rarity.is_not(None))
            .group_by(CardAttrs.rarity)
            .order_by(CardAttrs.rarity)
        )
    ]
    return {"sets": sets, "rarities": rarities}


@router.get("", response_model=CardListOut)
def list_cards(
    db: Session = Depends(get_db),
    search: str | None = None,
    set_code: str | None = None,
    rarity: str | None = None,
    collection: bool = True,
    limit: int = Query(120, le=300),
    offset: int = 0,
):
    """The card collection: owned cards by default (collection=false browses
    the full catalog, mostly for debugging)."""
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.cards.value)
    )
    filters = []
    if search:
        filters.append(CollectionItem.title.ilike(f"%{search}%"))
    if set_code:
        filters.append(CardAttrs.set_code == set_code)
    if rarity:
        filters.append(CardAttrs.rarity == rarity)
    if collection:
        filters.append(
            select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
        )
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(
            q.order_by(CardAttrs.national_dex_no.asc().nulls_last(), CollectionItem.title)
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )
    return CardListOut(total=total, items=[card_to_out(i) for i in items])


class HappyUpdate(BaseModel):
    happy: bool


@router.put("/pokedex/{dex_no}/happy")
def set_happy(dex_no: int, body: HappyUpdate, db: Session = Depends(get_db)):
    """'Happy with it' — this dex slot's keeper card stays even without an
    IR/SIR, so the binder stops flagging it for upgrade."""
    slot = db.get(DexSlot, dex_no)
    if slot is None:
        slot = DexSlot(dex_no=dex_no, happy=body.happy)
        db.add(slot)
    else:
        slot.happy = body.happy
    db.commit()
    return {"dex_no": dex_no, "happy": body.happy}


@router.get("/pokedex")
def pokedex(db: Session = Depends(get_db)):
    """The binder: one entry per national dex number (1..MAX_DEX), each with
    up to three layer occupants chosen from OWNED cards — the binder mirror."""
    # binder membership is opt-in per copy: only in_binder copies occupy slots
    owned_cards = (
        db.scalars(
            _base_query().where(
                CardAttrs.national_dex_no.is_not(None),
                select(Owned.id)
                .where(Owned.item_id == CollectionItem.id, Owned.in_binder)
                .exists(),
            )
        )
        .unique()
        .all()
    )

    # best occupant per (dex, layer): SIR beats IR in layer 3, then newest
    def rank(item):
        r = (item.card_attrs.rarity or "").lower()
        return (1 if "special" in r else 0, item.id)

    slots: dict[int, dict[int, CollectionItem]] = {}
    counts: dict[int, int] = {}
    for it in owned_cards:
        dex = it.card_attrs.national_dex_no
        if dex is None or dex > MAX_DEX:
            continue
        counts[dex] = counts.get(dex, 0) + sum(1 for o in it.owned if o.in_binder)
        layer = it.card_attrs.layer or 1
        cur = slots.setdefault(dex, {}).get(layer)
        if cur is None or rank(it) > rank(cur):
            slots[dex][layer] = it

    # display names for every dex number that exists in the catalog (shortest
    # title is a decent proxy for the plain species name)
    names: dict[int, str] = {}
    for dex, title in db.execute(
        select(CardAttrs.national_dex_no, CollectionItem.title)
        .join(CollectionItem, CollectionItem.id == CardAttrs.item_id)
        .where(CardAttrs.national_dex_no.is_not(None))
    ):
        if dex <= MAX_DEX and (dex not in names or len(title) < len(names[dex])):
            names[dex] = title

    happy = {
        s.dex_no for s in db.scalars(select(DexSlot).where(DexSlot.happy)).all()
    }

    def layer_out(item):
        if item is None:
            return None
        return {
            "id": item.id,
            # the binder copy itself, so the UI can pull it out of the binder
            "owned_id": next((o.id for o in item.owned if o.in_binder), None),
            "title": item.title,
            "image_url": item.image_url,
            "set_name": item.card_attrs.set_name,
            "card_number": item.card_attrs.card_number,
            "rarity": item.card_attrs.rarity,
        }

    entries = []
    for dex in range(1, MAX_DEX + 1):
        s = slots.get(dex, {})
        entries.append({
            "dex_no": dex,
            "name": names.get(dex),
            "layers": {
                "1": layer_out(s.get(1)),
                "2": layer_out(s.get(2)),
                "3": layer_out(s.get(3)),
            },
            "copies": counts.get(dex, 0),
            "happy": dex in happy,
        })
    return {"max_dex": MAX_DEX, "entries": entries}
