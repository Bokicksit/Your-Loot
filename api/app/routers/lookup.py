"""Barcode → product lookup, shared by games and movies.

Uses UPCitemdb's free trial tier (~100 lookups/day per IP, no key). The
returned product title feeds the module's metadata search (TMDB/IGDB);
for movies the title usually names the exact edition and format too.

It also returns retailer photographs of the product, which for a disc are
pictures of the actual case rather than the theatrical poster TMDB holds —
and being keyed on the barcode, they show the exact edition (steelbook,
reissue, 4K) that a film-level poster can't distinguish.
"""

import re
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/lookup", tags=["lookup"])

UPC_URL = "https://api.upcitemdb.com/prod/trial/lookup"
IMAGE_CAP = 8


def _size_hint(url: str) -> int:
    """Retailers declare the rendered size in the URL (`?odnHeight=450`,
    `/300x300/`). Read it so the sharpest image sorts first — guessing from
    any digits in the URL would score the hex in a filename instead."""
    parsed = urlparse(url)
    best = 0
    for key, values in parse_qs(parsed.query).items():
        # "wid"/"hei" rather than "width"/"height" — Target and Scene7 use the
        # short forms, and matching on those covers the long ones too
        if any(k in key.lower() for k in ("wid", "hei", "size")):
            best = max(best, *(int(v) for v in values if v.isdigit()), 0)
    for a, b in re.findall(r"(\d{2,4})x(\d{2,4})", parsed.path):
        best = max(best, int(a), int(b))
    return best


def _images(item: dict) -> list[str]:
    seen: set[str] = set()
    urls = []
    for url in item.get("images") or []:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return sorted(urls, key=_size_hint, reverse=True)[:IMAGE_CAP]


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
            {
                "title": it.get("title", ""),
                "brand": it.get("brand") or None,
                "images": _images(it),
            }
            for it in items[:5]
        ],
    }
