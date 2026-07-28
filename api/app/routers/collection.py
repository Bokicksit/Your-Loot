from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import CardAttrs, CollectionItem, GameAttrs, Module, Owned, Wanted
from app.schemas.collection import ItemStatusOut, WantedItemOut
from app.schemas.common import OwnedCreate, WantedCreate

router = APIRouter(prefix="/api", tags=["collection"])


def _get_item(db: Session, item_id: int) -> CollectionItem:
    item = db.get(CollectionItem, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    return item


def _status(item: CollectionItem) -> ItemStatusOut:
    return ItemStatusOut(item_id=item.id, owned=item.owned, wanted=item.wanted)


def _enforce_single_binder(db: Session, item: CollectionItem, keep_owned_id: int):
    """A binder holds ONE card per Pokémon: flagging a copy in_binder unflags
    any other binder copy sharing the same dex number (the physical swap)."""
    if item.module != Module.cards.value or not item.card_attrs:
        return
    dex = item.card_attrs.national_dex_no
    if dex is None:
        return
    others = db.scalars(
        select(Owned)
        .join(CollectionItem, CollectionItem.id == Owned.item_id)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            Owned.in_binder,
            Owned.id != keep_owned_id,
            CardAttrs.national_dex_no == dex,
        )
    ).all()
    for o in others:
        o.in_binder = False


@router.post("/items/{item_id}/owned", response_model=ItemStatusOut)
def add_owned(item_id: int, body: OwnedCreate, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    owned = Owned(item_id=item.id, **body.model_dump())
    db.add(owned)
    if body.in_binder:
        db.flush()
        _enforce_single_binder(db, item, owned.id)
    db.commit()
    db.refresh(item)
    return _status(item)


@router.patch("/items/{item_id}/owned/{owned_id}", response_model=ItemStatusOut)
def update_owned(
    item_id: int, owned_id: int, body: OwnedCreate, db: Session = Depends(get_db)
):
    """Edit a copy's condition/completeness/notes — e.g. filling them in after
    a 'Got it' acquisition. Only fields present in the request change."""
    item = _get_item(db, item_id)
    owned = db.get(Owned, owned_id)
    if not owned or owned.item_id != item.id:
        raise HTTPException(404, "owned record not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(owned, k, v)
    if data.get("in_binder"):
        _enforce_single_binder(db, item, owned.id)
    db.commit()
    db.refresh(item)
    return _status(item)


@router.delete("/items/{item_id}/owned/{owned_id}", response_model=ItemStatusOut)
def remove_owned(item_id: int, owned_id: int, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    owned = db.get(Owned, owned_id)
    if not owned or owned.item_id != item.id:
        raise HTTPException(404, "owned record not found")
    db.delete(owned)
    db.commit()
    db.refresh(item)
    return _status(item)


@router.post("/items/{item_id}/wanted", response_model=ItemStatusOut)
def add_wanted(item_id: int, body: WantedCreate, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    if item.wanted is None:
        db.add(Wanted(item_id=item.id, **body.model_dump()))
        db.commit()
        db.refresh(item)
    return _status(item)


@router.delete("/items/{item_id}/wanted", response_model=ItemStatusOut)
def remove_wanted(item_id: int, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    if item.wanted is not None:
        db.delete(item.wanted)
        # a games/movies entry that was wanted-only existed solely for the
        # wishlist — prune it, or it would surface in the library as an
        # unowned ghost row. Cards are catalog rows and always stay.
        if item.module != Module.cards.value and not item.owned:
            db.delete(item)
            db.commit()
            return ItemStatusOut(item_id=item_id, owned=[], wanted=None)
        db.commit()
        db.refresh(item)
    return _status(item)


def _detail(item: CollectionItem) -> str:
    """Per-module one-line summary so the wanted list UI stays module-agnostic."""
    if item.module == Module.cards.value and item.card_attrs:
        a = item.card_attrs
        parts = [a.set_name, f"#{a.card_number}" if a.card_number else None, a.variant]
    elif item.module == Module.games.value and item.game_attrs:
        a = item.game_attrs
        parts = [a.platform.name if a.platform else None, a.region,
                 "hardware" if a.is_hardware else None]
    elif item.module == Module.movies.value and item.movie_attrs:
        a = item.movie_attrs
        parts = [a.format, a.edition, a.region_code]
    else:
        parts = []
    return " · ".join(p for p in parts if p)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Per-module counts for the home screen tiles. `items` counts only
    titles with at least one owned copy — wanted-only entries belong to the
    Wanted tile, not the collection counts."""
    owned_exists = select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
    items = dict(
        db.execute(
            select(CollectionItem.module, func.count())
            .where(owned_exists)
            .group_by(CollectionItem.module)
        ).all()
    )
    owned = dict(
        db.execute(
            select(CollectionItem.module, func.count(Owned.id))
            .join(Owned, Owned.item_id == CollectionItem.id)
            .group_by(CollectionItem.module)
        ).all()
    )
    wanted = dict(
        db.execute(
            select(CollectionItem.module, func.count(Wanted.id))
            .join(Wanted, Wanted.item_id == CollectionItem.id)
            .group_by(CollectionItem.module)
        ).all()
    )
    return {
        m.value: {
            "items": items.get(m.value, 0),
            "owned": owned.get(m.value, 0),
            "wanted": wanted.get(m.value, 0),
        }
        for m in Module
    }


@router.get("/wanted", response_model=list[WantedItemOut])
def wanted_list(db: Session = Depends(get_db), module: str | None = None):
    """The unified wanted list — one query across all modules."""
    q = (
        select(Wanted)
        .join(CollectionItem)
        .options(
            joinedload(Wanted.item).joinedload(CollectionItem.card_attrs),
            joinedload(Wanted.item)
            .joinedload(CollectionItem.game_attrs)
            .joinedload(GameAttrs.platform),
            joinedload(Wanted.item).joinedload(CollectionItem.movie_attrs),
        )
        .order_by(Wanted.priority.asc().nulls_last(), Wanted.created_at)
    )
    if module:
        q = q.where(CollectionItem.module == module)
    def _facet(item: CollectionItem) -> str | None:
        """Sub-filter value: system for games, genre for movies."""
        if item.module == Module.games.value and item.game_attrs and item.game_attrs.platform:
            p = item.game_attrs.platform
            return p.abbreviation or p.name
        if item.module == Module.movies.value and item.movie_attrs:
            return item.movie_attrs.genre
        return None

    def _info(item: CollectionItem) -> tuple[str, str | None]:
        """Expandable row info: (facts line, optional longer text)."""
        parts: list = []
        text = None
        if item.module == Module.cards.value and item.card_attrs:
            a = item.card_attrs
            parts = [a.set_name, a.set_year, a.rarity]
        elif item.module == Module.games.value and item.game_attrs:
            a = item.game_attrs
            parts = [
                a.release_year,
                a.genres,
                a.developer and f"Dev: {a.developer}",
                a.publisher and a.publisher != a.developer and f"Pub: {a.publisher}",
            ]
            text = a.summary
        elif item.module == Module.movies.value and item.movie_attrs:
            a = item.movie_attrs
            parts = [a.genre]
            text = a.overview
        line = "  ·  ".join(str(p) for p in parts if p)
        return line, text

    def _badge(item: CollectionItem) -> str | None:
        """Left-edge row badge: system for games, media format for movies."""
        if item.module == Module.games.value and item.game_attrs and item.game_attrs.platform:
            p = item.game_attrs.platform
            return p.abbreviation or p.name
        if item.module == Module.movies.value and item.movie_attrs:
            return item.movie_attrs.format
        return None

    rows = db.scalars(q).unique().all()
    out = []
    for w in rows:
        line, text = _info(w.item)
        out.append(
            WantedItemOut(
                item_id=w.item.id,
                module=w.item.module,
                title=w.item.title,
                image_url=w.item.image_url,
                detail=_detail(w.item),
                facet=_facet(w.item),
                badge=_badge(w.item),
                info_line=line,
                info_text=text,
                wanted=w,
            )
        )
    return out
