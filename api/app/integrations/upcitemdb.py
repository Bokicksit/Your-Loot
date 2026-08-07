"""UPCitemdb — barcode to product title and retailer photographs.

Free trial tier: no key, roughly 100 lookups a day per IP.

Shared rather than living in the lookup router, because it's also the fallback
when a music database has never heard of a pressing: retailers list records the
catalogues miss, and the listing carries the artist, the album and a photo of
the actual sleeve.
"""

import re
from urllib.parse import parse_qs, urlparse

import httpx

URL = "https://api.upcitemdb.com/prod/trial/lookup"
SEARCH_URL = "https://api.upcitemdb.com/prod/trial/search"
IMAGE_CAP = 8


class BarcodeError(Exception):
    """Carries an HTTP status the routers can translate for their own callers."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


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


def lookup(code: str) -> list[dict]:
    """Products matching a barcode, most complete first. Empty list = no match."""
    digits = "".join(ch for ch in code if ch.isdigit())
    try:
        resp = httpx.get(URL, params={"upc": digits}, timeout=15)
    except httpx.HTTPError as e:
        raise BarcodeError(502, f"barcode service unreachable: {e}")
    if resp.status_code == 429:
        raise BarcodeError(
            429,
            "Barcode lookups exhausted for today (free tier) — type the title instead",
        )
    if resp.status_code == 400:
        raise BarcodeError(400, "That doesn't scan as a valid UPC/EAN")
    resp.raise_for_status()
    return [
        {
            "title": it.get("title", ""),
            "brand": it.get("brand") or None,
            "images": _images(it),
        }
        for it in resp.json().get("items", [])[:5]
    ]


def search(keyword: str, limit: int = 8) -> list[dict]:
    """Retail listings matching a name — the route to a photograph of the case
    for something added by title rather than scanned.

    The metadata catalogues have nothing like this: TMDB holds 229 posters for
    Blade Runner 2049 and every one is a 2:3 theatrical poster, while a shop
    listing carries the actual keep case. Same daily budget as a barcode
    lookup, and a short burst cap on top, so this runs on an explicit pick —
    never on a keystroke.
    """
    term = (keyword or "").strip()
    if len(term) < 3:
        return []
    try:
        resp = httpx.get(SEARCH_URL, params={"s": term}, timeout=15)
    except httpx.HTTPError as e:
        raise BarcodeError(502, f"product search unreachable: {e}")
    if resp.status_code == 429:
        raise BarcodeError(429, "Product lookups exhausted for now (free tier)")
    if resp.status_code >= 400:
        raise BarcodeError(502, f"product search error: {resp.status_code}")
    out = []
    for it in resp.json().get("items", [])[:limit]:
        images = _images(it)
        if not images:
            continue  # a listing with no picture is no use here
        out.append({"title": it.get("title", ""), "brand": it.get("brand") or None,
                    "images": images})
    return out
