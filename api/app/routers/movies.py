import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.integrations.tmdb import tmdb_client
from app.models import CollectionItem, Module, MovieAttrs, Owned, Wanted
from app.schemas.movies import MovieAttrsOut, MovieCreate, MovieListOut, MovieOut

router = APIRouter(prefix="/api/movies", tags=["movies"])


def movie_to_out(item: CollectionItem) -> MovieOut:
    a = item.movie_attrs
    return MovieOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=MovieAttrsOut(
            format=a.format,
            edition=a.edition,
            region_code=a.region_code,
            tmdb_id=a.tmdb_id,
        ),
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(MovieAttrs, MovieAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.movies.value)
        .options(
            joinedload(CollectionItem.movie_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/tmdb/search")
def tmdb_search(q: str = Query(min_length=2)):
    if not tmdb_client.configured:
        raise HTTPException(503, "TMDB not configured — set TMDB_API_KEY")
    try:
        return tmdb_client.search_movies(q)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"TMDB error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TMDB unreachable: {e}")


@router.get("/formats")
def list_formats(db: Session = Depends(get_db)):
    """Formats present in the collection (library view), with counts —
    mirrors the games platform filter."""
    owned_exists = select(Owned.id).where(Owned.item_id == MovieAttrs.item_id).exists()
    wanted_exists = select(Wanted.id).where(Wanted.item_id == MovieAttrs.item_id).exists()
    rows = db.execute(
        select(MovieAttrs.format, func.count())
        .where(MovieAttrs.format.is_not(None))
        .where(owned_exists | ~wanted_exists)
        .group_by(MovieAttrs.format)
        .order_by(MovieAttrs.format)
    ).all()
    return [{"format": f, "count": c} for f, c in rows]


@router.get("", response_model=MovieListOut)
def list_movies(
    db: Session = Depends(get_db),
    search: str | None = None,
    format: str | None = None,
    sort: str = Query("title", pattern="^(title|format|added)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(MovieAttrs, MovieAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.movies.value)
    )
    filters = []
    if search:
        filters.append(CollectionItem.title.ilike(f"%{search}%"))
    if format:
        filters.append(MovieAttrs.format == format)

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
    elif sort == "format":
        order = [MovieAttrs.format.asc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    )
    return MovieListOut(total=total, items=[movie_to_out(i) for i in items])


@router.post("", response_model=MovieOut, status_code=201)
def create_movie(body: MovieCreate, db: Session = Depends(get_db)):
    """Manual or TMDB-prefilled. No dedupe on tmdb_id — the same film may
    exist once per physical edition (Blu-ray, 4K steelbook, …)."""
    item = CollectionItem(
        module=Module.movies.value,
        source="tmdb" if body.tmdb_id is not None else "manual",
        title=body.title,
        image_url=body.image_url,
        notes=body.notes,
        movie_attrs=MovieAttrs(
            format=body.format,
            edition=body.edition,
            region_code=body.region_code,
            tmdb_id=body.tmdb_id,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return movie_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_movie(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.movies.value:
        raise HTTPException(404, "movie not found")
    db.delete(item)
    db.commit()
