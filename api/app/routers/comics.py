import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.integrations.comicvine import comicvine_client
from app.models import CollectionItem, ComicAttrs, Module, Owned, Wanted, User
from app.search import contains
from app.sorting import leading_number
from app.tenancy import my_copies, my_want, on_my_shelf
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


def comic_to_out(item: CollectionItem, uid: int) -> ComicOut:
    a = item.comic_attrs
    return ComicOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=ComicAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
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
def search_comicvine(
    q: str | None = None,
    series: str | None = None,
    issue: str | None = None,
    year: int | None = None,
):
    """Look an issue up on Comic Vine.

    Given a series and an issue number it goes via the run, which is the only
    way to say *which* Guardians of the Galaxy #1 you mean. `year` is the run's
    start year, not the cover year. Anything less specific falls back to the
    full-text search, sorted so the year asked for comes first.
    """
    if not comicvine_client.configured:
        raise HTTPException(503, "Comic Vine not configured — set COMICVINE_API_KEY")
    series = (series or "").strip()
    issue = (issue or "").strip()
    broad = (q or "").strip() or " ".join(p for p in (series, issue) if p)
    if not broad:
        raise HTTPException(400, "give a series and issue number to search for")
    if series and issue:
        try:
            hits = comicvine_client.find(series, issue, year)
            if hits:
                return hits
        except httpx.HTTPError:
            # the precise route is an optimisation; if Comic Vine doesn't like
            # the filter, the broad search below still answers the question
            pass
    try:
        return comicvine_client.search(broad, volume_year=year)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(502, "Comic Vine rejected the API key")
        raise HTTPException(502, f"Comic Vine error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Comic Vine unreachable: {e}")


@router.get("/facets")
def comic_facets(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Series and publishers present in the collection, for the filters."""
    _shelf = on_my_shelf(user.id, ComicAttrs.item_id)
    on_shelf = _shelf

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
    user: User = Depends(current_user),
    search: str | None = None,
    series: str | None = None,
    publisher: str | None = None,
    sort: str = Query("series", pattern="^(series|title|publisher|year|added|oldest)$"),
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
    # A shelf is what you own; the Wanted tab is where a wish lives. Asking
    # for both is what include_wanted_only means.
    filters.append(on_my_shelf(user.id, CollectionItem.id, include_wanted_only))
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "title":
        order = [CollectionItem.title]
    elif sort == "publisher":
        order = [
            ComicAttrs.publisher.asc().nulls_last(),
            ComicAttrs.series.asc().nulls_last(),
            leading_number(ComicAttrs.issue_number).asc().nulls_last(),
            CollectionItem.title,
        ]
    elif sort == "year":
        order = [ComicAttrs.cover_year.desc().nulls_last(), CollectionItem.title]
    else:
        # a long box is filed by series then issue. issue_number is text
        # because plenty of issues aren't numbers ("1A", "½", "Annual"), so
        # sort on the number it starts with and let the text break ties —
        # that puts #9 before #10, which plain text ordering does not. The
        # ones with no number at all trail their series.
        order = [
            ComicAttrs.series.asc().nulls_last(),
            ComicAttrs.volume_year.asc().nulls_last(),
            leading_number(ComicAttrs.issue_number).asc().nulls_last(),
            ComicAttrs.issue_number,
        ]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    return ComicListOut(total=total, items=[comic_to_out(i, user.id) for i in items])


@router.post("", response_model=ComicOut, status_code=201)
def create_comic(body: ComicCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
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
    return comic_to_out(item, user.id)


@router.patch("/{item_id}", response_model=ComicOut)
def update_comic(item_id: int, body: ComicUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
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
    return comic_to_out(item, user.id)


@router.delete("/{item_id}", status_code=204)
def delete_comic(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.comics.value:
        raise HTTPException(404, "issue not found")
    db.delete(item)
    db.commit()
