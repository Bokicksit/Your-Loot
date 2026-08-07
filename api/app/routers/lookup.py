"""Barcode → product lookup, shared by games, movies and hardware.

The returned product title feeds the module's metadata search (TMDB/IGDB); for
movies the title usually names the exact edition and format too.

It also returns retailer photographs of the product, which for a disc or a boxed
console are pictures of the actual case rather than the promotional art — and
being keyed on the barcode, they show the exact edition a film-level poster
can't distinguish.
"""

from fastapi import APIRouter, HTTPException, Query

from app.integrations.upcitemdb import (
    BarcodeError,
    lookup as upc_lookup,
    search as upc_search,
)

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


@router.get("/barcode")
def barcode(code: str = Query(pattern=r"^\d{8,14}$")):
    try:
        items = upc_lookup(code)
    except BarcodeError as e:
        raise HTTPException(e.status, e.message)
    return {"found": bool(items), "titles": items}


@router.get("/products")
def products(q: str = Query(min_length=3, max_length=120)):
    """Retail listings by name, for their photographs of the actual packaging.

    Answers with an empty list rather than an error when the free tier is
    spent: artwork is a bonus on top of an entry that saves perfectly well
    without it, and failing the whole add for it would be absurd.
    """
    try:
        return {"items": upc_search(q)}
    except BarcodeError as e:
        if e.status == 429:
            return {"items": [], "exhausted": True}
        raise HTTPException(e.status, e.message)
