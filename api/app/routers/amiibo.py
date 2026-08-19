"""amiibo — the ninth collection, and the second one with a full catalogue.

Cards set the pattern this follows: the whole product line is seeded into
the shared catalogue (932 figures and cards, from the open amiibo database),
so adding one is searching what is already here and picking it — no external
API at add time, no key, no rate limit. Manual entry stays for the figure
the catalogue has never heard of, which at this line's size is the exception.

The identity is the head+tail hex id Nintendo burned into the figure — what
an NFC reader sees — kept as source="amiibo" + external_id, which is what
lets a personal restore find the same figure on another install.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.models import AmiiboAttrs, CollectionItem, Module, User
from app.search import contains
from app.tagging import tagged, tags_for, tags_of
from app.tenancy import my_copies, my_want, on_my_shelf, visible
from app.schemas.amiibo import (
    AmiiboAttrsOut,
    AmiiboCreate,
    AmiiboListOut,
    AmiiboOut,
    AmiiboUpdate,
)

router = APIRouter(prefix="/api/amiibo", tags=["amiibo"])

ATTR_FIELDS = (
    "amiibo_id", "character", "amiibo_series", "game_series",
    "figure_type", "release_year", "release_na",
)


def amiibo_to_out(item: CollectionItem, uid: int, tags=()) -> AmiiboOut:
    a = item.amiibo_attrs
    return AmiiboOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=AmiiboAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        # passed in, not looked up: one query for the page beats one per row
        tags=list(tags),
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(AmiiboAttrs, AmiiboAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.amiibo.value)
        .options(
            joinedload(CollectionItem.amiibo_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search")
def search_catalogue(
    q: str | None = None,
    series: str | None = None,
    figure_type: str | None = None,
    limit: int = Query(60, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """The seeded catalogue, which is where an amiibo comes from.

    Unlike the collections that ask an external API, this searches what the
    seed already put in the shared catalogue — instant, keyless, and the
    same 932 answers on every install that has run the seed.
    """
    filters = [visible(user.id)]
    if q and q.strip():
        term = q.strip()
        filters.append(
            contains(CollectionItem.title, term)
            | contains(AmiiboAttrs.character, term)
            | contains(AmiiboAttrs.amiibo_series, term)
            | contains(AmiiboAttrs.game_series, term)
        )
    if series:
        filters.append(AmiiboAttrs.amiibo_series == series)
    if figure_type:
        filters.append(AmiiboAttrs.figure_type == figure_type)

    items = db.scalars(
        _base_query()
        .where(*filters)
        .order_by(AmiiboAttrs.amiibo_series, CollectionItem.title)
        .limit(limit)
    ).unique().all()
    return {
        "items": [amiibo_to_out(i, user.id) for i in items],
        "seeded": bool(
            db.scalar(
                select(CollectionItem.id)
                .where(
                    CollectionItem.module == Module.amiibo.value,
                    CollectionItem.source == "amiibo",
                )
                .limit(1)
            )
        ),
    }


@router.get("/facets")
def amiibo_facets(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Series and types present in the collection, for the filters."""
    on_shelf = on_my_shelf(user.id, AmiiboAttrs.item_id)

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
        "series": facet(AmiiboAttrs.amiibo_series),
        "types": facet(AmiiboAttrs.figure_type),
    }


@router.get("", response_model=AmiiboListOut)
def list_amiibo(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = None,
    series: str | None = None,
    figure_type: str | None = None,
    tag: str | None = None,
    sort: str = Query("series", pattern="^(series|title|character|year|added|oldest)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(AmiiboAttrs, AmiiboAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.amiibo.value)
    )
    # Rows somebody imported and nobody else agreed to stay with them. First
    # in the list because it is not a filter the caller asked for — it is the
    # boundary the rest of the query runs inside.
    filters = [visible(user.id)]
    if search:
        filters.append(
            contains(CollectionItem.title, search)
            | contains(AmiiboAttrs.character, search)
            | contains(AmiiboAttrs.amiibo_series, search)
        )
    if series:
        filters.append(AmiiboAttrs.amiibo_series == series)
    if figure_type:
        filters.append(AmiiboAttrs.figure_type == figure_type)
    if tag:
        filters.append(tagged(user.id, "amiibo", tag, CollectionItem.id))
    # A shelf is what you own; the Wanted tab is where a wish lives. Asking
    # for both is what include_wanted_only means.
    filters.append(on_my_shelf(user.id, CollectionItem.id, include_wanted_only))
    q = q.where(*filters)
    count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "title":
        order = [CollectionItem.title]
    elif sort == "character":
        order = [AmiiboAttrs.character.asc().nulls_last(), CollectionItem.title]
    elif sort == "year":
        order = [AmiiboAttrs.release_year.desc().nulls_last(), CollectionItem.title]
    else:
        # by series, the way a shelf of them is actually arranged
        order = [
            AmiiboAttrs.amiibo_series.asc().nulls_last(),
            CollectionItem.title,
        ]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return AmiiboListOut(
        total=total,
        items=[amiibo_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.post("", response_model=AmiiboOut, status_code=201)
def create_amiibo(body: AmiiboCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Manual entry — a prototype, a fake worth cataloguing as one, or a
    figure newer than the seed. Everything else is in the catalogue already."""
    item = CollectionItem(
        module=Module.amiibo.value,
        source="manual",
        title=body.title.strip(),
        image_url=body.image_url,
        notes=body.notes,
        amiibo_attrs=AmiiboAttrs(
            **{f: getattr(body, f, None) for f in ATTR_FIELDS if hasattr(body, f)}
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return amiibo_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.patch("/{item_id}", response_model=AmiiboOut)
def update_amiibo(item_id: int, body: AmiiboUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.amiibo.value:
        raise HTTPException(404, "amiibo not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.amiibo_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return amiibo_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.delete("/{item_id}", status_code=204)
def delete_amiibo(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.amiibo.value:
        raise HTTPException(404, "amiibo not found")
    if item.source == "amiibo":
        # A catalogue row is everybody's — deleting it would empty this
        # figure out of every collection on the server. Removing your copy
        # is done on the copy, and the row stays for the next person.
        raise HTTPException(409, "that is a catalogue entry — remove your copy instead")
    db.delete(item)
    db.commit()
