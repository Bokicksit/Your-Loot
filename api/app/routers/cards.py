import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
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
        s = set.strip()
        # match the set name OR the code printed on modern cards (MEW, JTG)
        q = q.where(
            or_(
                CardAttrs.set_name.ilike(f"%{s}%"),
                func.upper(CardAttrs.set_abbr) == s.upper(),
            )
        )

    items = (
        db.scalars(q.order_by(CardAttrs.set_code, CollectionItem.title).limit(limit))
        .unique()
        .all()
    )
    return CardListOut(total=len(items), items=[card_to_out(i) for i in items])


@router.get("/facets")
def card_facets(db: Session = Depends(get_db), include_binder: bool = False):
    """Sets and rarities present among OWNED cards, with counts — drives the
    collection filter dropdowns. Mirrors the list's binder-hiding default."""
    owned_q = select(Owned.id).where(Owned.item_id == CardAttrs.item_id)
    if not include_binder:
        owned_q = owned_q.where(~Owned.in_binder)
    owned_exists = owned_q.exists()
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
    include_binder: bool = False,
    limit: int = Query(120, le=300),
    offset: int = 0,
):
    """The card collection: owned cards by default (collection=false browses
    the full catalog, mostly for debugging). Binder-only cards are hidden
    unless include_binder — the binder is its own view."""
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
        owned_q = select(Owned.id).where(Owned.item_id == CollectionItem.id)
        if not include_binder:
            owned_q = owned_q.where(~Owned.in_binder)
        filters.append(owned_q.exists())
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
    """The binder: one entry per national dex number, ONE occupant each (the
    copy flagged in_binder). `final` = this is the desired card for that
    Pokémon; otherwise it's a placeholder awaiting an upgrade."""
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

    # normally one binder card per dex (enforced on write); for legacy
    # multiples prefer the fancier card, then the newest
    def rank(item):
        a = item.card_attrs
        r = (a.rarity or "").lower()
        return (a.layer or 1, 1 if "special" in r else 0, item.id)

    slots: dict[int, CollectionItem] = {}
    for it in owned_cards:
        dex = it.card_attrs.national_dex_no
        if dex is None or dex > MAX_DEX:
            continue
        if dex not in slots or rank(it) > rank(slots[dex]):
            slots[dex] = it

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

    final = {
        s.dex_no for s in db.scalars(select(DexSlot).where(DexSlot.happy)).all()
    }

    def card_out(item):
        if item is None:
            return None
        a = item.card_attrs
        binder_copy = next((o for o in item.owned if o.in_binder), None)
        return {
            "id": item.id,
            # the binder copy itself, so the UI can pull it out of the binder
            "owned_id": binder_copy.id if binder_copy else None,
            "title": item.title,
            "image_url": item.image_url,
            "set_name": a.set_name,
            "set_abbr": a.set_abbr,
            "set_total": a.set_total,
            "set_year": a.set_year,
            "card_number": a.card_number,
            "rarity": a.rarity,
            "layer": a.layer or 1,
            # print details of the copy actually sleeved in the binder
            "variant": binder_copy.variant if binder_copy else None,
            "stamp": binder_copy.stamp if binder_copy else None,
            "condition": binder_copy.condition if binder_copy else None,
            "grader": binder_copy.grader if binder_copy else None,
            "grade": binder_copy.grade if binder_copy else None,
        }

    entries = []
    for dex in range(1, MAX_DEX + 1):
        entries.append({
            "dex_no": dex,
            "name": names.get(dex),
            "card": card_out(slots.get(dex)),
            "final": dex in final,
        })
    return {"max_dex": MAX_DEX, "entries": entries}
