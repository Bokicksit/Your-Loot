import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.integrations.openlibrary import openlibrary_client
from app.barcodes import lookup as cached_lookup
from app.integrations.upcitemdb import BarcodeError
from app.models import BookAttrs, CollectionItem, Module, Owned, Wanted, User
from app.ratelimit import outbound
from app.search import contains
from app.tagging import tagged, tags_for, tags_of
from app.tenancy import guard_entry_write, my_copies, my_want, on_my_shelf, visible
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


def book_to_out(item: CollectionItem, uid: int, tags=()) -> BookOut:
    a = item.book_attrs
    return BookOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=BookAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        # passed in, not looked up: one query for the page beats one per row
        tags=list(tags),
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


def _jacket(db, isbn: str) -> str | None:
    """A cover from the retail listing for this ISBN.

    Open Library's bibliographic data is good but its cover coverage is thin —
    plenty of editions carry a title, author and page count with no picture at
    all. An ISBN-13 is a barcode, so the shops that stock the book usually have
    a photograph of the jacket.
    """
    try:
        products = cached_lookup(db, isbn)
    except BarcodeError:
        return None  # a missing cover shouldn't fail the whole lookup
    for p in products:
        if p.get("images"):
            return p["images"][0]
    return None


@router.get("/search", dependencies=[Depends(outbound)])
def search_openlibrary(
    q: str | None = None,
    isbn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Look a book up in Open Library — by ISBN (the barcode on the back) or
    by title/author text. An ISBN with no cover in Open Library borrows one
    from the retail listing rather than showing a blank tile."""
    try:
        if isbn and isbn.strip():
            hit = openlibrary_client.by_isbn(isbn)
            if hit and hit.get("image_url"):
                return [hit]
            jacket = _jacket(db, isbn)
            if hit:
                hit["image_url"] = jacket
                return [hit]
            # nothing bibliographic, but the shops may still know the book
            if jacket:
                products = cached_lookup(db, isbn)
                return [{
                    "title": products[0]["title"],
                    "author": None,
                    "publisher": None,
                    "isbn": "".join(ch for ch in isbn if ch.isalnum()),
                    "publish_year": None,
                    "page_count": None,
                    "image_url": jacket,
                    "olid": None,
                }]
            return []
        if not (q or "").strip():
            raise HTTPException(400, "give a search term or an ISBN")
        return openlibrary_client.search(q)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Open Library unreachable: {e}")


@router.get("/description", dependencies=[Depends(outbound)])
def book_description(
    olid: str = Query(min_length=3, max_length=30),
    user: User = Depends(current_user),
):
    """The blurb for one book, fetched only once it's been chosen.

    Its own route rather than a field on the search results: it costs an extra
    request per book, sometimes two, and a page of twenty results would pay
    that twenty times over for nineteen books nobody picked.
    """
    return {"description": openlibrary_client.description(olid)}


@router.get("/facets")
def book_facets(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Authors and formats present in the collection, for the filters."""
    _shelf = on_my_shelf(user.id, BookAttrs.item_id)
    in_library = _shelf
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
    user: User = Depends(current_user),
    search: str | None = None,
    author: str | None = None,
    format: str | None = None,
    tag: str | None = None,
    sort: str = Query("title", pattern="^(title|author|series|year|added|oldest)$"),
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
    # Rows somebody imported and nobody else agreed to stay with them. First
    # in the list because it is not a filter the caller asked for — it is the
    # boundary the rest of the query runs inside.
    filters = [visible(user.id)]
    if search:
        filters.append(
            contains(CollectionItem.title, search) | contains(BookAttrs.author, search)
        )
    if author:
        filters.append(BookAttrs.author == author)
    if format:
        filters.append(BookAttrs.format == format)
    # A shelf is what you own; the Wanted tab is where a wish lives. Asking
    if tag:
        filters.append(tagged(user.id, "books", tag, CollectionItem.id))
    # for both is what include_wanted_only means.
    filters.append(on_my_shelf(user.id, CollectionItem.id, include_wanted_only))
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "author":
        order = [BookAttrs.author.asc().nulls_last(), CollectionItem.title]
    elif sort == "series":
        # a series reads in order, so date beats alphabet within one; the
        # standalones fall to the end rather than jumbling into the runs
        order = [
            BookAttrs.series.asc().nulls_last(),
            BookAttrs.publish_year.asc().nulls_last(),
            CollectionItem.title,
        ]
    elif sort == "year":
        order = [BookAttrs.publish_year.desc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return BookListOut(
        total=total,
        items=[book_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.post("", response_model=BookOut, status_code=201)
def create_book(body: BookCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
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
    return book_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.patch("/{item_id}", response_model=BookOut)
def update_book(item_id: int, body: BookUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.books.value:
        raise HTTPException(404, "book not found")
    guard_entry_write(db, item, user)
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.book_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return book_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.delete("/{item_id}", status_code=204)
def delete_book(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.books.value:
        raise HTTPException(404, "book not found")
    guard_entry_write(db, item, user, deleting=True)
    db.delete(item)
    db.commit()
