"""Barcode → product lookup, shared by games, movies and hardware.

The returned product title feeds the module's metadata search (TMDB/IGDB); for
movies the title usually names the exact edition and format too.

It also returns retailer photographs of the product, which for a disc or a boxed
console are pictures of the actual case rather than the promotional art — and
being keyed on the barcode, they show the exact edition a film-level poster
can't distinguish.
"""

from fastapi import APIRouter, HTTPException, Query

from app.integrations.upcitemdb import BarcodeError, lookup as upc_lookup

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


@router.get("/barcode")
def barcode(code: str = Query(pattern=r"^\d{8,14}$")):
    try:
        items = upc_lookup(code)
    except BarcodeError as e:
        raise HTTPException(e.status, e.message)
    return {"found": bool(items), "titles": items}
