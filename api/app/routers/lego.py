import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.integrations.rebrickable import rebrickable_client
from app.models import CollectionItem, LegoAttrs, Module, Owned, Wanted, User
from app.search import contains
from app.sorting import leading_number
from app.tenancy import my_copies, my_want, on_my_shelf
from app.schemas.lego import (
    LegoAttrsOut,
    LegoCreate,
    LegoListOut,
    LegoOut,
    LegoUpdate,
)

router = APIRouter(prefix="/api/lego", tags=["lego"])

ATTR_FIELDS = (
    "set_number", "theme", "subtheme", "release_year",
    "piece_count", "minifig_count", "barcode",
)


def lego_to_out(item: CollectionItem, uid: int) -> LegoOut:
    a = item.lego_attrs
    return LegoOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=LegoAttrsOut(**{f: getattr(a, f) for f in ATTR_FIELDS}),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(LegoAttrs, LegoAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.lego.value)
        .options(
            joinedload(CollectionItem.lego_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search")
def search_rebrickable(q: str | None = None, set_number: str | None = None):
    """Look a set up on Rebrickable — by set number (printed on the box) or by
    name."""
    if not rebrickable_client.configured:
        raise HTTPException(
            503, "Rebrickable not configured — set REBRICKABLE_API_KEY"
        )
    try:
        if set_number and set_number.strip():
            return rebrickable_client.search(set_number=set_number)
        if not (q or "").strip():
            raise HTTPException(400, "give a search term or a set number")
        return rebrickable_client.search(query=q)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(502, "Rebrickable rejected the API key")
        raise HTTPException(502, f"Rebrickable error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Rebrickable unreachable: {e}")


@router.get("/facets")
def lego_facets(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Themes and years present in the collection, for the filters."""
    _shelf = on_my_shelf(user.id, LegoAttrs.item_id)
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

    return {"themes": facet(LegoAttrs.theme), "years": facet(LegoAttrs.release_year)}


@router.get("", response_model=LegoListOut)
def list_lego(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = None,
    theme: str | None = None,
    sort: str = Query("title", pattern="^(title|theme|number|year|pieces|added|oldest)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(LegoAttrs, LegoAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.lego.value)
    )
    filters = []
    if search:
        filters.append(
            contains(CollectionItem.title, search)
            | contains(LegoAttrs.set_number, search)
            | contains(LegoAttrs.theme, search)
        )
    if theme:
        filters.append(LegoAttrs.theme == theme)
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
    elif sort == "theme":
        order = [LegoAttrs.theme.asc().nulls_last(), CollectionItem.title]
    elif sort == "number":
        # numerically, so 4002 files before 10179 — and roughly chronologically
        # as a side effect, since LEGO hands set numbers out as it goes
        order = [
            leading_number(LegoAttrs.set_number).asc().nulls_last(),
            LegoAttrs.set_number.asc().nulls_last(),
            CollectionItem.title,
        ]
    elif sort == "year":
        order = [LegoAttrs.release_year.desc().nulls_last(), CollectionItem.title]
    elif sort == "pieces":
        order = [LegoAttrs.piece_count.desc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    return LegoListOut(total=total, items=[lego_to_out(i, user.id) for i in items])


@router.post("", response_model=LegoOut, status_code=201)
def create_lego(body: LegoCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """No dedupe on set number: owning two of the same set is normal — one
    built, one sealed — and they're tracked as separate copies or entries."""
    item = CollectionItem(
        module=Module.lego.value,
        source="rebrickable" if body.set_number else "manual",
        title=body.title.strip(),
        image_url=body.image_url,
        notes=body.notes,
        lego_attrs=LegoAttrs(**{f: getattr(body, f) for f in ATTR_FIELDS}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return lego_to_out(item, user.id)


@router.patch("/{item_id}", response_model=LegoOut)
def update_lego(item_id: int, body: LegoUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.lego.value:
        raise HTTPException(404, "set not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in ATTR_FIELDS:
        if field in data:
            setattr(item.lego_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return lego_to_out(item, user.id)


@router.delete("/{item_id}", status_code=204)
def delete_lego(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.lego.value:
        raise HTTPException(404, "set not found")
    db.delete(item)
    db.commit()
