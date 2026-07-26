from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import CardAttrs, CollectionItem, Module
from app.schemas.cards import CardListOut, CardOut, PokedexEntry, PokedexOut

router = APIRouter(prefix="/api/cards", tags=["cards"])


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


@router.get("", response_model=CardListOut)
def list_cards(
    db: Session = Depends(get_db),
    search: str | None = None,
    set_code: str | None = None,
    rarity: str | None = None,
    dex: int | None = None,
    limit: int = Query(60, le=200),
    offset: int = 0,
):
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
    if dex is not None:
        filters.append(CardAttrs.national_dex_no == dex)
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(
            q.order_by(CardAttrs.set_code, CardAttrs.national_dex_no, CollectionItem.title)
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )
    return CardListOut(total=total, items=[card_to_out(i) for i in items])


@router.get("/pokedex", response_model=PokedexOut)
def pokedex(db: Session = Depends(get_db), owned_only: bool = False):
    """Cards grouped by national dex number. The UI renders this as the
    Pokédex grid; owned_only trims to slots where you own at least one card."""
    items = (
        db.scalars(
            _base_query()
            .where(CardAttrs.national_dex_no.is_not(None))
            .order_by(CardAttrs.national_dex_no, CollectionItem.title)
        )
        .unique()
        .all()
    )

    by_dex: dict[int, list[CollectionItem]] = {}
    for item in items:
        by_dex.setdefault(item.card_attrs.national_dex_no, []).append(item)

    entries = []
    for dex_no, group in sorted(by_dex.items()):
        owned_cards = [i for i in group if i.owned]
        if owned_only and not owned_cards:
            continue
        display = owned_cards[0] if owned_cards else group[0]
        entries.append(
            PokedexEntry(
                dex_no=dex_no,
                display_title=display.title,
                display_image=display.image_url,
                owned_count=sum(len(i.owned) for i in group),
                card_count=len(group),
                cards=[card_to_out(i) for i in group],
            )
        )
    return PokedexOut(entries=entries)
