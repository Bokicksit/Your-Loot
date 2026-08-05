"""MusicBrainz client — free, no API key, CC0 data.

Vinyl-shaped: a release carries the label, catalogue number and the physical
format ('12" Vinyl'), which is what identifies a pressing. Cover art comes
from the Cover Art Archive, keyed on the same release id.

MusicBrainz asks for one request per second and a descriptive User-Agent;
both are honoured here.
"""

import threading
import time

import httpx

API = "https://musicbrainz.org/ws/2"
COVER = "https://coverartarchive.org/release/{}/front-500"
UA = {"User-Agent": "your-loot/1.0 (self-hosted collection tracker)"}

_lock = threading.Lock()
_last_call = 0.0


def _throttled_get(url: str, params: dict) -> dict:
    """MusicBrainz rate limit is 1 req/sec — serialise and space our calls."""
    global _last_call
    with _lock:
        wait = 1.05 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        r = httpx.get(url, params=params, headers=UA, timeout=25, follow_redirects=True)
        _last_call = time.monotonic()
    r.raise_for_status()
    return r.json()


def _artist(rel: dict) -> str | None:
    names = [a["name"] for a in rel.get("artist-credit", []) if isinstance(a, dict) and "name" in a]
    return ", ".join(names) or None


def _summarise(rel: dict) -> dict:
    media = rel.get("media") or []
    labels = rel.get("label-info") or []
    date = rel.get("date") or ""
    return {
        "mbid": rel.get("id"),
        "title": rel.get("title"),
        "artist": _artist(rel),
        "release_year": int(date[:4]) if date[:4].isdigit() else None,
        "country": rel.get("country"),
        "barcode": rel.get("barcode") or None,
        "label": next(((l.get("label") or {}).get("name") for l in labels if l.get("label")), None),
        "catalog_number": next((l.get("catalog-number") for l in labels if l.get("catalog-number")), None),
        # "12\" Vinyl" x2 -> "2x12\" Vinyl"
        "format": _format(media),
        "track_count": sum(m.get("track-count") or 0 for m in media) or None,
        "image_url": COVER.format(rel["id"]) if rel.get("id") else None,
    }


def _format(media: list) -> str | None:
    if not media:
        return None
    kinds = [m.get("format") for m in media if m.get("format")]
    if not kinds:
        return None
    first = kinds[0]
    return f"{len(kinds)}x{first}" if len(kinds) > 1 else first


def _vinyl_rank(rel: dict) -> int:
    """MusicBrainz ranks by text relevance alone, so a Spotify single or a
    covers album outranks the pressing you're holding. This is a records
    collection — put wax first, other physical media next, digital last.
    Nothing is dropped: a CD in your crate is still findable."""
    fmt = (rel.get("format") or "").lower()
    if "vinyl" in fmt or fmt.startswith("shellac"):
        return 0
    if not fmt or "digital" in fmt or "file" in fmt:
        return 2
    return 1


def _phrase(value: str) -> str:
    """Quote a value for a Lucene field query, escaping what would end it."""
    return '"' + value.strip().replace("\\", "\\\\").replace('"', '\\"') + '"'


class MusicBrainzClient:
    def search(self, query: str | None = None, artist: str | None = None,
               barcode: str | None = None, limit: int = 20) -> list[dict]:
        title, artist = (query or "").strip(), (artist or "").strip()
        if barcode and barcode.strip():
            q = f'barcode:{"".join(ch for ch in barcode if ch.isdigit())}'
        elif title and artist:
            # field-scoped, or a covers compilation by someone else outranks
            # the pressing the collector actually typed the artist for
            q = f"artist:{_phrase(artist)} AND release:{_phrase(title)}"
        elif artist:
            q = f"artist:{_phrase(artist)}"
        elif title:
            q = title
        else:
            return []
        # over-fetch so vinyl buried below digital noise can still surface,
        # then rank and cut — ranking a truncated list would hide it instead
        data = _throttled_get(
            f"{API}/release/",
            {"query": q, "fmt": "json", "limit": min(100, max(limit * 3, 50))},
        )
        hits = [_summarise(r) for r in data.get("releases", [])]
        # sorted() is stable, so MusicBrainz's relevance order survives within
        # each rank
        return sorted(hits, key=_vinyl_rank)[:limit]

    def get_release(self, mbid: str) -> dict:
        data = _throttled_get(
            f"{API}/release/{mbid}",
            {"fmt": "json", "inc": "artist-credits+labels+media"},
        )
        return _summarise(data)


musicbrainz_client = MusicBrainzClient()
