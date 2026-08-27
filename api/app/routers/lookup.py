"""Barcode → product lookup, shared by games, movies and hardware.

The returned product title feeds the module's metadata search (TMDB/IGDB); for
movies the title usually names the exact edition and format too.

It also returns retailer photographs of the product, which for a disc or a boxed
console are pictures of the actual case rather than the promotional art — and
being keyed on the barcode, they show the exact edition a film-level poster
can't distinguish.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.barcodes import lookup as cached_lookup
from app.db import get_db
from app.auth import current_user
from app.integrations.upcitemdb import BarcodeError, search as upc_search
from app.ratelimit import outbound

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


@router.get("/barcode", dependencies=[Depends(outbound)])
def barcode(
    code: str = Query(pattern=r"^\d{8,14}$"),
    db=Depends(get_db),
    user=Depends(current_user),
):
    try:
        items = cached_lookup(db, code)
    except BarcodeError as e:
        raise HTTPException(e.status, e.message)
    return {"found": bool(items), "titles": items}


@router.get("/products", dependencies=[Depends(outbound)])
def products(
    q: str = Query(min_length=3, max_length=120),
    require_images: bool = True,
    user=Depends(current_user),
):
    """Retail listings by name, for their photographs of the actual packaging.

    Answers with an empty list rather than an error when the free tier is
    spent: artwork is a bonus on top of an entry that saves perfectly well
    without it, and failing the whole add for it would be absurd.
    """
    try:
        return {"items": upc_search(q, require_images=require_images)}
    except BarcodeError as e:
        if e.status == 429:
            return {"items": [], "exhausted": True}
        raise HTTPException(e.status, e.message)
