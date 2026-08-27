import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.integrations.tmdb import tmdb_client
from app.models import CollectionItem, Module, MovieAttrs, Owned, Wanted, User
from app.ratelimit import outbound
from app.tagging import tagged, tags_for, tags_of
from app.tenancy import guard_entry_write, my_copies, my_want, on_my_shelf, visible
from app.schemas.movies import (
    MovieAttrsOut,
    MovieCreate,
    MovieListOut,
    MovieOut,
    MovieUpdate,
)
from app.search import contains
from app.sorting import year_from_title

router = APIRouter(prefix="/api/movies", tags=["movies"])


def movie_to_out(item: CollectionItem, uid: int, tags=()) -> MovieOut:
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
            genre=a.genre,
            overview=a.overview,
            tmdb_id=a.tmdb_id,
        ),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        # passed in, not looked up: one query for the page beats one per row
        tags=list(tags),
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


@router.get("/tmdb/search", dependencies=[Depends(outbound)])
def tmdb_search(q: str = Query(min_length=2), user: User = Depends(current_user)):
    if not tmdb_client.configured:
        raise HTTPException(503, "TMDB not configured — set TMDB_API_KEY")
    try:
        return tmdb_client.search_movies(q)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"TMDB error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TMDB unreachable: {e}")


@router.get("/formats")
def list_formats(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Formats present in the collection (library view), with counts —
    mirrors the games platform filter."""
    _shelf = on_my_shelf(user.id, MovieAttrs.item_id)
    rows = db.execute(
        select(MovieAttrs.format, func.count())
        .where(MovieAttrs.format.is_not(None))
        .where(_shelf)
        .group_by(MovieAttrs.format)
        .order_by(MovieAttrs.format)
    ).all()
    return [{"format": f, "count": c} for f, c in rows]


@router.get("", response_model=MovieListOut)
def list_movies(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = None,
    format: str | None = None,
    tag: str | None = None,
    sort: str = Query("title", pattern="^(title|format|year|added|oldest)$"),
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
    # Rows somebody imported and nobody else agreed to stay with them. First
    # in the list because it is not a filter the caller asked for — it is the
    # boundary the rest of the query runs inside.
    filters = [visible(user.id)]
    if search:
        filters.append(contains(CollectionItem.title, search))
    if format:
        filters.append(MovieAttrs.format == format)

    # A shelf is what you own; the Wanted tab is where a wish lives. Asking
    if tag:
        filters.append(tagged(user.id, "movies", tag, CollectionItem.id))
    # for both is what include_wanted_only means.
    filters.append(on_my_shelf(user.id, CollectionItem.id, include_wanted_only))

    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "format":
        order = [MovieAttrs.format.asc().nulls_last(), CollectionItem.title]
    elif sort == "year":
        # films have no year column: the "(2017)" TMDB search appends to the
        # title is the only copy of it we hold
        order = [
            year_from_title(CollectionItem.title).desc().nulls_last(),
            CollectionItem.title,
        ]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    )
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return MovieListOut(
        total=total,
        items=[movie_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.post("", response_model=MovieOut, status_code=201)
def create_movie(body: MovieCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
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
            genre=body.genre,
            overview=body.overview,
            tmdb_id=body.tmdb_id,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return movie_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.patch("/{item_id}", response_model=MovieOut)
def update_movie(item_id: int, body: MovieUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.movies.value:
        raise HTTPException(404, "movie not found")
    guard_entry_write(db, item, user)
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ("format", "edition", "region_code", "genre"):
        if field in data:
            setattr(item.movie_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return movie_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.delete("/{item_id}", status_code=204)
def delete_movie(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.movies.value:
        raise HTTPException(404, "movie not found")
    guard_entry_write(db, item, user, deleting=True)
    db.delete(item)
    db.commit()
