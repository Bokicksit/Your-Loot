import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.integrations.openlibrary import openlibrary_client
from app.models import BookAttrs, CollectionItem, Module, Owned, Wanted
from app.schemas.books import (
    BookAttrsOut,
    BookCreate,
    BookListOut,
    BookOut,
    BookUpdate,
)

router = APIRouter(prefix="/api/books", tags=["books"])

ATTR_FIELDS = (
    "author", "publisher", "isbn", "format", "edition",
    "publish_year", "page_count", "series", "blurb",
)


def book_to_out(item: CollectionItem) -> BookOut:
    a = item.book_attrs
    return BookOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=BookAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(BookAttrs, BookAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.books.value)
        .options(
            joinedload(CollectionItem.book_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search")
def search_openlibrary(
    q: str | None = None, isbn: str | None = None
):
    """Look a book up in Open Library — by ISBN (the barcode on the back) or
    by title/author text."""
    try:
        if isbn and isbn.strip():
            hit = openlibrary_client.by_isbn(isbn)
            return [hit] if hit else []
        if not (q or "").strip():
            raise HTTPException(400, "give a search term or an ISBN")
        return openlibrary_client.search(q)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Open Library unreachable: {e}")


@router.get("/facets")
def book_facets(db: Session = Depends(get_db)):
    """Authors and formats present in the collection, for the filters."""
    owned_exists = select(Owned.id).where(Owned.item_id == BookAttrs.item_id).exists()
    wanted_exists = select(Wanted.id).where(Wanted.item_id == BookAttrs.item_id).exists()
    in_library = owned_exists | ~wanted_exists
    authors = [
        {"author": a, "count": c}
        for a, c in db.execute(
            select(BookAttrs.author, func.count())
            .where(in_library, BookAttrs.author.is_not(None))
            .group_by(BookAttrs.author)
            .order_by(BookAttrs.author)
        )
    ]
    formats = [
        {"format": f, "count": c}
        for f, c in db.execute(
            select(BookAttrs.format, func.count())
            .where(in_library, BookAttrs.format.is_not(None))
            .group_by(BookAttrs.format)
            .order_by(BookAttrs.format)
        )
    ]
    return {"authors": authors, "formats": formats}


@router.get("", response_model=BookListOut)
def list_books(
    db: Session = Depends(get_db),
    search: str | None = None,
    author: str | None = None,
    format: str | None = None,
    sort: str = Query("title", pattern="^(title|author|added|year)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(BookAttrs, BookAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.books.value)
    )
    filters = []
    if search:
        term = f"%{search}%"
        filters.append(CollectionItem.title.ilike(term) | BookAttrs.author.ilike(term))
    if author:
        filters.append(BookAttrs.author == author)
    if format:
        filters.append(BookAttrs.format == format)
    if not include_wanted_only:
        # library view: wanted-but-unowned books live on the Wanted tab only
        owned_exists = select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
        wanted_exists = select(Wanted.id).where(Wanted.item_id == CollectionItem.id).exists()
        filters.append(owned_exists | ~wanted_exists)
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "author":
        order = [BookAttrs.author.asc().nulls_last(), CollectionItem.title]
    elif sort == "year":
        order = [BookAttrs.publish_year.desc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    return BookListOut(total=total, items=[book_to_out(i) for i in items])


@router.post("", response_model=BookOut, status_code=201)
def create_book(body: BookCreate, db: Session = Depends(get_db)):
    """Books repeat legitimately — a paperback and a first-edition hardcover
    of the same title are different objects — so there's no ISBN dedupe."""
    item = CollectionItem(
        module=Module.books.value,
        source="openlibrary" if body.isbn else "manual",
        title=body.title.strip(),
        image_url=body.image_url,
        notes=body.notes,
        book_attrs=BookAttrs(**{f: getattr(body, f) for f in ATTR_FIELDS}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return book_to_out(item)


@router.patch("/{item_id}", response_model=BookOut)
def update_book(item_id: int, body: BookUpdate, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.books.value:
        raise HTTPException(404, "book not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.book_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return book_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_book(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.books.value:
        raise HTTPException(404, "book not found")
    db.delete(item)
    db.commit()
