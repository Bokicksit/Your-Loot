import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.integrations.igdb import igdb_client
from app.models import CollectionItem, GameAttrs, Module, Owned, Platform, Wanted
from app.schemas.games import GameAttrsOut, GameCreate, GameListOut, GameOut, GameUpdate

router = APIRouter(prefix="/api/games", tags=["games"])


def game_to_out(item: CollectionItem) -> GameOut:
    a = item.game_attrs
    return GameOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=GameAttrsOut(
            platform_id=a.platform_id,
            platform_name=a.platform.name if a.platform else None,
            platform_abbr=a.platform.abbreviation if a.platform else None,
            region=a.region,
            is_hardware=a.is_hardware,
            summary=a.summary,
            release_year=a.release_year,
            genres=a.genres,
            developer=a.developer,
            publisher=a.publisher,
        ),
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(GameAttrs, GameAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.games.value)
        .options(
            joinedload(CollectionItem.game_attrs).joinedload(GameAttrs.platform),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/platforms")
def list_platforms(db: Session = Depends(get_db), in_use: bool = False):
    """Full lookup for the add form; in_use=true returns only platforms that
    have at least one collection entry (with counts) — used by the filter UI."""
    if in_use:
        # mirror the library view: wanted-only entries don't count here either
        owned_exists = select(Owned.id).where(Owned.item_id == GameAttrs.item_id).exists()
        wanted_exists = select(Wanted.id).where(Wanted.item_id == GameAttrs.item_id).exists()
        rows = db.execute(
            select(Platform, func.count(GameAttrs.item_id))
            .join(GameAttrs, GameAttrs.platform_id == Platform.id)
            .where(owned_exists | ~wanted_exists)
            .group_by(Platform.id)
            .order_by(Platform.name)
        ).all()
        return [
            {"id": p.id, "name": p.name, "abbreviation": p.abbreviation, "count": c}
            for p, c in rows
        ]
    rows = db.scalars(select(Platform).order_by(Platform.name)).all()
    return [{"id": p.id, "name": p.name, "abbreviation": p.abbreviation} for p in rows]


@router.get("/igdb/search")
def igdb_search(q: str = Query(min_length=2)):
    if not igdb_client.configured:
        raise HTTPException(
            503, "IGDB not configured — set IGDB_CLIENT_ID / IGDB_CLIENT_SECRET"
        )
    try:
        return igdb_client.search_games(q)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"IGDB error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"IGDB unreachable: {e}")


@router.get("", response_model=GameListOut)
def list_games(
    db: Session = Depends(get_db),
    search: str | None = None,
    platform_id: int | None = None,
    is_hardware: bool | None = None,
    sort: str = Query("title", pattern="^(title|platform|added)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(GameAttrs, GameAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.games.value)
    )
    filters = []
    if search:
        filters.append(CollectionItem.title.ilike(f"%{search}%"))
    if platform_id is not None:
        filters.append(GameAttrs.platform_id == platform_id)
    if is_hardware is not None:
        filters.append(GameAttrs.is_hardware == is_hardware)
    if not include_wanted_only:
        # library view: wanted-but-unowned entries live on the Wanted tab only
        owned_exists = select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
        wanted_exists = select(Wanted.id).where(Wanted.item_id == CollectionItem.id).exists()
        filters.append(owned_exists | ~wanted_exists)

    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "platform":
        q = q.outerjoin(Platform, GameAttrs.platform_id == Platform.id)
        order = [Platform.name.asc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    )
    return GameListOut(total=total, items=[game_to_out(i) for i in items])


@router.post("", response_model=GameOut, status_code=201)
def create_game(body: GameCreate, db: Session = Depends(get_db)):
    """Manual entry, or IGDB-prefilled when igdb_id is set (dedupes on it)."""
    if body.platform_id is not None and db.get(Platform, body.platform_id) is None:
        raise HTTPException(400, "unknown platform_id")
    if body.igdb_id is not None:
        existing = db.scalar(
            select(CollectionItem).where(
                CollectionItem.source == "igdb",
                CollectionItem.external_id == str(body.igdb_id),
            )
        )
        if existing:
            raise HTTPException(409, f"'{existing.title}' is already in your catalog")
    item = CollectionItem(
        module=Module.games.value,
        source="igdb" if body.igdb_id is not None else "manual",
        external_id=str(body.igdb_id) if body.igdb_id is not None else None,
        title=body.title,
        image_url=body.image_url,
        notes=body.notes,
        game_attrs=GameAttrs(
            platform_id=body.platform_id,
            region=body.region,
            is_hardware=body.is_hardware,
            summary=body.summary,
            release_year=body.release_year,
            genres=body.genres,
            developer=body.developer,
            publisher=body.publisher,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return game_to_out(item)


@router.patch("/{item_id}", response_model=GameOut)
def update_game(item_id: int, body: GameUpdate, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.games.value:
        raise HTTPException(404, "game not found")
    data = body.model_dump(exclude_unset=True)
    if "platform_id" in data and data["platform_id"] is not None:
        if db.get(Platform, data["platform_id"]) is None:
            raise HTTPException(400, "unknown platform_id")
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ("platform_id", "region", "is_hardware"):
        if field in data:
            setattr(item.game_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return game_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_game(item_id: int, db: Session = Depends(get_db)):
    """Removes the catalog entry AND its owned/wanted records (cascade) —
    meant for fixing manual-entry mistakes, not for 'I sold this'."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.games.value:
        raise HTTPException(404, "game not found")
    db.delete(item)
    db.commit()
