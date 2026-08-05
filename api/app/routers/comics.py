import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.integrations.comicvine import comicvine_client
from app.models import CollectionItem, ComicAttrs, Module, Owned, Wanted
from app.search import contains
from app.schemas.comics import (
    ComicAttrsOut,
    ComicCreate,
    ComicListOut,
    ComicOut,
    ComicUpdate,
)

router = APIRouter(prefix="/api/comics", tags=["comics"])

ATTR_FIELDS = (
    "series", "issue_number", "volume_year", "publisher", "cover_year",
    "variant", "creators", "barcode", "blurb",
)


def comic_to_out(item: CollectionItem) -> ComicOut:
    a = item.comic_attrs
    return ComicOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=ComicAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(ComicAttrs, ComicAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.comics.value)
        .options(
            joinedload(CollectionItem.comic_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search")
def search_comicvine(q: str | None = None):
    """Look an issue up on Comic Vine, e.g. 'Saga 1' or 'Amazing Spider-Man 300'."""
    if not comicvine_client.configured:
        raise HTTPException(503, "Comic Vine not configured — set COMICVINE_API_KEY")
    if not (q or "").strip():
        raise HTTPException(400, "give a series and issue number to search for")
    try:
        return comicvine_client.search(q)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(502, "Comic Vine rejected the API key")
        raise HTTPException(502, f"Comic Vine error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Comic Vine unreachable: {e}")


@router.get("/facets")
def comic_facets(db: Session = Depends(get_db)):
    """Series and publishers present in the collection, for the filters."""
    owned_exists = select(Owned.id).where(Owned.item_id == ComicAttrs.item_id).exists()
    wanted_exists = select(Wanted.id).where(Wanted.item_id == ComicAttrs.item_id).exists()
    on_shelf = owned_exists | ~wanted_exists

    def facet(col):
        return [
            {"value": v, "count": c}
            for v, c in db.execute(
                select(col, func.count())
                .where(on_shelf, col.is_not(None))
                .group_by(col)
                .order_by(col)
            )
        ]

    return {
        "series": facet(ComicAttrs.series),
        "publishers": facet(ComicAttrs.publisher),
    }


@router.get("", response_model=ComicListOut)
def list_comics(
    db: Session = Depends(get_db),
    search: str | None = None,
    series: str | None = None,
    publisher: str | None = None,
    sort: str = Query("series", pattern="^(series|title|added|year)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(ComicAttrs, ComicAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.comics.value)
    )
    filters = []
    if search:
        filters.append(
            contains(CollectionItem.title, search)
            | contains(ComicAttrs.series, search)
            | contains(ComicAttrs.creators, search)
        )
    if series:
        filters.append(ComicAttrs.series == series)
    if publisher:
        filters.append(ComicAttrs.publisher == publisher)
    if not include_wanted_only:
        # shelf view: wanted-but-unowned issues live on the Wanted tab only
        owned_exists = select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
        wanted_exists = select(Wanted.id).where(Wanted.item_id == CollectionItem.id).exists()
        filters.append(owned_exists | ~wanted_exists)
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "title":
        order = [CollectionItem.title]
    elif sort == "year":
        order = [ComicAttrs.cover_year.desc().nulls_last(), CollectionItem.title]
    else:
        # a long box is filed by series then issue; issue_number is text
        # ("1A", "½") so it can't sort numerically without a cast that would
        # break on those
        order = [
            ComicAttrs.series.asc().nulls_last(),
            ComicAttrs.volume_year.asc().nulls_last(),
            func.length(ComicAttrs.issue_number),
            ComicAttrs.issue_number,
        ]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    return ComicListOut(total=total, items=[comic_to_out(i) for i in items])


@router.post("", response_model=ComicOut, status_code=201)
def create_comic(body: ComicCreate, db: Session = Depends(get_db)):
    """No dedupe: variant covers of one issue are different books to a
    collector, and owning two of the same is normal."""
    item = CollectionItem(
        module=Module.comics.value,
        source="comicvine" if body.series else "manual",
        title=body.title.strip(),
        image_url=body.image_url,
        notes=body.notes,
        comic_attrs=ComicAttrs(**{f: getattr(body, f) for f in ATTR_FIELDS}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return comic_to_out(item)


@router.patch("/{item_id}", response_model=ComicOut)
def update_comic(item_id: int, body: ComicUpdate, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.comics.value:
        raise HTTPException(404, "issue not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.comic_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return comic_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_comic(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.comics.value:
        raise HTTPException(404, "issue not found")
    db.delete(item)
    db.commit()
