import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.integrations.discogs import discogs_client
from app.integrations.musicbrainz import musicbrainz_client
from app.integrations.upcitemdb import BarcodeError, lookup as upc_lookup
from app.models import CollectionItem, Module, Owned, RecordAttrs, Wanted
from app.search import contains
from app.schemas.records import (
    RecordAttrsOut,
    RecordCreate,
    RecordListOut,
    RecordOut,
    RecordUpdate,
)

router = APIRouter(prefix="/api/records", tags=["records"])

ATTR_FIELDS = (
    "artist", "label", "catalog_number", "format", "speed", "pressing",
    "release_year", "country", "barcode", "track_count", "tracklist",
)


def record_to_out(item: CollectionItem) -> RecordOut:
    a = item.record_attrs
    return RecordOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=RecordAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=item.owned,
        wanted=item.wanted,
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(RecordAttrs, RecordAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.records.value)
        .options(
            joinedload(CollectionItem.record_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


# Words a retailer pads a listing with that are never part of an album title.
_PRODUCT_NOISE = re.compile(
    r"^(vinyl|lp|record|records|album|cd|cassette|music|performance|import|"
    r"explicit|remastered|reissue|new|sealed|\d+\s*lp|\d+\s*disc)$",
    re.I,
)


def _from_product(item: dict, barcode: str) -> dict:
    """Turn a retailer listing into something the add form can use.

    Listings read "Artist - Album - Genre - Vinyl", so the first two segments
    are what matter and the rest is shelf-category padding.
    """
    parts = [p.strip() for p in (item.get("title") or "").split(" - ") if p.strip()]
    meaningful = [p for p in parts if not _PRODUCT_NOISE.match(p)]
    artist = meaningful[0] if len(meaningful) > 1 else None
    title = meaningful[1] if len(meaningful) > 1 else (meaningful[0] if meaningful else None)
    blob = " ".join(parts).lower()
    fmt = None
    if "cassette" in blob:
        fmt = "Cassette"
    elif re.search(r"\bcd\b", blob):
        fmt = "CD"
    elif "vinyl" in blob or re.search(r"\blp\b", blob):
        fmt = '12" Vinyl'
    return {
        "mbid": None,
        "title": title,
        "artist": artist,
        "label": item.get("brand"),
        "catalog_number": None,
        "format": fmt,
        "release_year": None,
        "country": None,
        # the one thing this result is certain about
        "barcode": "".join(ch for ch in barcode if ch.isdigit()),
        "track_count": None,
        "image_url": (item.get("images") or [None])[0],
        "source": "barcode",
    }


@router.get("/search")
def search_musicbrainz(
    q: str | None = None, artist: str | None = None, barcode: str | None = None
):
    """Look a pressing up in MusicBrainz — by barcode (the scan on the sleeve),
    or by album title and artist. `q` is the album title; passing `artist` too
    scopes the query to that artist instead of matching title text alone.

    MusicBrainz records barcodes unevenly, especially on older pressings, so a
    scan that finds nothing there falls back to the retailer database: it knows
    the sleeve even when the music catalogue doesn't, and what it returns is
    enough to search MusicBrainz by name instead of leaving you at a dead end.
    """
    try:
        if barcode and barcode.strip():
            # Discogs leads: it's catalogued by people describing the record in
            # their hands, so it carries pressings the others have never heard
            # of. A dead token shouldn't take the whole scan down with it.
            if discogs_client.configured:
                try:
                    hits = discogs_client.by_barcode(barcode)
                    if hits:
                        return hits
                except httpx.HTTPError:
                    pass
            hits = musicbrainz_client.search(barcode=barcode)
            if hits:
                return hits
            try:
                products = upc_lookup(barcode)
            except BarcodeError:
                products = []  # the fallback failing shouldn't mask "not found"
            if not products:
                return []
            found = _from_product(products[0], barcode)
            # the retailer's own listing first — it matches the barcode exactly —
            # then whatever MusicBrainz has under that name, for the pressing
            # details a shop listing never carries
            named = (
                musicbrainz_client.search(query=found["title"], artist=found["artist"])
                if found["title"]
                else []
            )
            return [found, *named]
        if not (q or "").strip() and not (artist or "").strip():
            raise HTTPException(400, "give an album, an artist or a barcode")
        # Discogs leads by name for the same reason it leads by barcode: it is
        # catalogued by people describing the record in their hands, so it
        # carries pressings MusicBrainz has never heard of. Typing the album in
        # used to reach only MusicBrainz, which made a scan and a search of the
        # same record answer differently.
        if discogs_client.configured:
            try:
                hits = discogs_client.search(query=q, artist=artist)
                if hits:
                    return hits
            except httpx.HTTPError:
                pass  # a dead token shouldn't take the search down with it
        return musicbrainz_client.search(query=q, artist=artist)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"MusicBrainz unreachable: {e}")


@router.get("/tracklist")
def record_tracklist(release_id: str):
    """The running order for one Discogs pressing.

    Its own route, fetched only once a pressing has been chosen: it is a
    request per record, and a page of search results would spend ten of them
    on nine records nobody picked.
    """
    return {"tracklist": discogs_client.tracklist(release_id)}


@router.get("/facets")
def record_facets(db: Session = Depends(get_db)):
    """Artists, labels and formats present in the collection, for the filters."""
    owned_exists = select(Owned.id).where(Owned.item_id == RecordAttrs.item_id).exists()
    wanted_exists = select(Wanted.id).where(Wanted.item_id == RecordAttrs.item_id).exists()
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
        "artists": facet(RecordAttrs.artist),
        "labels": facet(RecordAttrs.label),
        "formats": facet(RecordAttrs.format),
    }


@router.get("", response_model=RecordListOut)
def list_records(
    db: Session = Depends(get_db),
    search: str | None = None,
    artist: str | None = None,
    label: str | None = None,
    format: str | None = None,
    sort: str = Query("artist", pattern="^(artist|title|label|year|added|oldest)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(RecordAttrs, RecordAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.records.value)
    )
    filters = []
    if search:
        filters.append(
            contains(CollectionItem.title, search)
            | contains(RecordAttrs.artist, search)
            | contains(RecordAttrs.catalog_number, search)
        )
    if artist:
        filters.append(RecordAttrs.artist == artist)
    if label:
        filters.append(RecordAttrs.label == label)
    if format:
        filters.append(RecordAttrs.format == format)
    if not include_wanted_only:
        # shelf view: wanted-but-unowned records live on the Wanted tab only
        owned_exists = select(Owned.id).where(Owned.item_id == CollectionItem.id).exists()
        wanted_exists = select(Wanted.id).where(Wanted.item_id == CollectionItem.id).exists()
        filters.append(owned_exists | ~wanted_exists)
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "title":
        order = [CollectionItem.title]
    elif sort == "label":
        # a label run files by catalogue number, which is how the label
        # numbered them and therefore roughly the order they came out
        order = [
            RecordAttrs.label.asc().nulls_last(),
            RecordAttrs.catalog_number.asc().nulls_last(),
            CollectionItem.title,
        ]
    elif sort == "year":
        order = [RecordAttrs.release_year.desc().nulls_last(), CollectionItem.title]
    else:
        # crates are filed by artist, so that's the default
        order = [RecordAttrs.artist.asc().nulls_last(), CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    return RecordListOut(total=total, items=[record_to_out(i) for i in items])


@router.post("", response_model=RecordOut, status_code=201)
def create_record(body: RecordCreate, db: Session = Depends(get_db)):
    """No dedupe on barcode: owning two copies of the same pressing is normal,
    and a repress shares almost everything with the original but is a different
    record."""
    item = CollectionItem(
        module=Module.records.value,
        source="musicbrainz" if body.barcode else "manual",
        title=body.title.strip(),
        image_url=body.image_url,
        notes=body.notes,
        record_attrs=RecordAttrs(**{f: getattr(body, f) for f in ATTR_FIELDS}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return record_to_out(item)


@router.patch("/{item_id}", response_model=RecordOut)
def update_record(item_id: int, body: RecordUpdate, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.records.value:
        raise HTTPException(404, "record not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.record_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return record_to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_record(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.records.value:
        raise HTTPException(404, "record not found")
    db.delete(item)
    db.commit()
