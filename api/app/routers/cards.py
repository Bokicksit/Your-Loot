import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

import httpx

from app.cards_util import classify_layer
from app.db import get_db
from app.integrations.tcgdex import tcgdex_client
from app.models import CardAttrs, CollectionItem, DexSlot, Module, Owned, Wanted
from app.schemas.cards import CardCreate, CardListOut, CardOut, CardUpdate

router = APIRouter(prefix="/api/cards", tags=["cards"])

MAX_DEX = 1025  # current national dex (through Scarlet & Violet)


def card_to_out(item: CollectionItem) -> CardOut:
    return CardOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        source=item.source,
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
        # match the set name, the code printed on modern cards (MEW, JTG),
        # or the dump's internal set id (sv3pt5) as a last resort
        q = q.where(
            or_(
                CardAttrs.set_name.ilike(f"%{s}%"),
                func.upper(CardAttrs.set_abbr) == s.upper(),
                func.lower(CardAttrs.set_code) == s.lower(),
            )
        )

    items = (
        db.scalars(q.order_by(CardAttrs.set_code, CollectionItem.title).limit(limit))
        .unique()
        .all()
    )
    return CardListOut(total=len(items), items=[card_to_out(i) for i in items])


@router.get("/sets")
def list_sets(db: Session = Depends(get_db), q: str | None = None):
    """Every set in the card database, newest first — powers the set
    autocomplete so the printed codes are discoverable, and makes a missing
    reseed obvious (abbr shows null)."""
    stmt = select(
        CardAttrs.set_code,
        CardAttrs.set_name,
        CardAttrs.set_abbr,
        CardAttrs.set_year,
        func.max(CardAttrs.set_total),
    ).group_by(
        CardAttrs.set_code, CardAttrs.set_name, CardAttrs.set_abbr, CardAttrs.set_year
    )
    if q:
        s = q.strip()
        stmt = stmt.where(
            or_(
                CardAttrs.set_name.ilike(f"%{s}%"),
                CardAttrs.set_abbr.ilike(f"{s}%"),
                CardAttrs.set_code.ilike(f"{s}%"),
            )
        )
    rows = db.execute(
        stmt.order_by(CardAttrs.set_year.desc().nulls_last(), CardAttrs.set_name)
    ).all()
    return [
        {"code": c, "name": n, "abbr": a, "year": y, "total": t}
        for c, n, a, y, t in rows
    ]


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


@router.get("/tcgdex/search")
def tcgdex_search(
    name: str | None = None,
    set: str | None = None,
    number: str | None = None,
):
    """Look the card up in TCGdex — the open catalog that carries cards our
    offline dump lacks (new promo sets, and later additions to ongoing promo
    sets). Needs a name, or a set plus number."""
    if not (name or "").strip() and not (set or "").strip():
        raise HTTPException(400, "give a card name, or a set and number")
    try:
        results = tcgdex_client.search_cards(name=name, set_id=set, number=number)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return []
        raise HTTPException(502, f"TCGdex error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TCGdex unreachable: {e}")
    return results


@router.post("/tcgdex/{card_id}", response_model=CardOut, status_code=201)
def add_from_tcgdex(card_id: str, db: Session = Depends(get_db)):
    """Import a TCGdex card into the local catalog. Keyed on
    (source='tcgdex', external_id) so re-importing returns the same row and a
    dump reseed can never clobber it."""
    existing = db.scalar(
        select(CollectionItem).where(
            CollectionItem.source == "tcgdex", CollectionItem.external_id == card_id
        )
    )
    if existing:
        return card_to_out(existing)
    try:
        d = tcgdex_client.get_card(card_id)
    except httpx.HTTPStatusError:
        raise HTTPException(404, "card not found in TCGdex")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TCGdex unreachable: {e}")

    item = CollectionItem(
        module=Module.cards.value,
        source="tcgdex",
        external_id=card_id,
        title=d["title"],
        image_url=d["image_url"],
        card_attrs=CardAttrs(
            set_code=d["set_id"],
            set_name=d["set_name"],
            set_abbr=(d["set_id"] or "").upper()[:10] or None,
            card_number=d["card_number"],
            set_total=d["set_total"],
            rarity=d["rarity"],
            national_dex_no=d["national_dex_no"],
            layer=classify_layer(d["rarity"]),
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return card_to_out(item)


@router.post("", response_model=CardOut, status_code=201)
def create_card(body: CardCreate, db: Session = Depends(get_db)):
    """Add a card the dump doesn't have yet. A later reseed can't clobber it:
    upserts key on (source='ptcg', external_id) and these are source='manual'."""
    item = CollectionItem(
        module=Module.cards.value,
        source="manual",
        title=body.title.strip(),
        image_url=body.image_url,
        card_attrs=CardAttrs(
            set_name=body.set_name,
            set_abbr=body.set_abbr.upper() if body.set_abbr else None,
            set_code=None,
            card_number=body.card_number,
            set_total=body.set_total,
            set_year=body.set_year,
            rarity=body.rarity,
            national_dex_no=body.national_dex_no,
            layer=classify_layer(body.rarity),
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return card_to_out(item)


@router.patch("/{item_id}", response_model=CardOut)
def update_card(item_id: int, body: CardUpdate, db: Session = Depends(get_db)):
    """Edit a manual card (including its photo). Dump-sourced rows are
    read-only — a reseed would overwrite any edit anyway."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.cards.value:
        raise HTTPException(404, "card not found")
    data = body.model_dump(exclude_unset=True)
    # dump rows get their fields rewritten by every reseed, so only the image
    # may be overridden there — the seeder preserves locally-stored images.
    # Manual and TCGdex rows are yours to correct entirely.
    if item.source not in ("manual", "tcgdex") and set(data) - {"image_url"}:
        raise HTTPException(
            400, "only the image can be changed on cards from the card database"
        )
    if "title" in data:
        item.title = data["title"].strip()
    if "image_url" in data:
        item.image_url = data["image_url"]
    for field in (
        "set_name", "set_abbr", "card_number", "set_total", "set_year",
        "rarity", "national_dex_no",
    ):
        if field in data:
            val = data[field]
            if field == "set_abbr" and val:
                val = val.upper()
            setattr(item.card_attrs, field, val)
    if "rarity" in data:
        item.card_attrs.layer = classify_layer(data["rarity"])
    db.commit()
    db.refresh(item)
    return card_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_card(item_id: int, db: Session = Depends(get_db)):
    """Only manual entries can be deleted — dump-sourced catalog rows stay
    (removing your copies is what takes a card out of the collection)."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.cards.value:
        raise HTTPException(404, "card not found")
    if item.source not in ("manual", "tcgdex"):
        raise HTTPException(
            400,
            "cards from the offline dump can't be deleted; remove your copies instead",
        )
    db.delete(item)
    db.commit()


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
