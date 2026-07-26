"""Barcode → product title lookup, shared by games and movies.

Uses UPCitemdb's free trial tier (~100 lookups/day per IP, no key). The
returned product title feeds the module's metadata search (TMDB/IGDB);
for movies the title usually names the exact edition and format too.
"""

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/lookup", tags=["lookup"])

UPC_URL = "https://api.upcitemdb.com/prod/trial/lookup"


@router.get("/barcode")
def barcode(code: str = Query(pattern=r"^\d{8,14}$")):
    try:
        resp = httpx.get(UPC_URL, params={"upc": code}, timeout=15)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"barcode service unreachable: {e}")
    if resp.status_code == 429:
        raise HTTPException(429, "Barcode lookups exhausted for today (free tier) — type the title instead")
    if resp.status_code == 400:
        raise HTTPException(400, "That doesn't scan as a valid UPC/EAN")
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return {
        "found": bool(items),
        "titles": [
            {"title": it.get("title", ""), "brand": it.get("brand") or None}
            for it in items[:5]
        ],
    }
