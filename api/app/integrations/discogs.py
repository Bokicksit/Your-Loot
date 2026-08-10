"""Discogs client — the pressing-level database for records.

Free personal access token from https://www.discogs.com/settings/developers
("Generate token"). Set it as DISCOGS_TOKEN.

Why it leads for records: Discogs is catalogued by collectors describing the
exact object in their hands, so its barcode coverage on vinyl runs well past
MusicBrainz's — limited runs and boutique repressings that MusicBrainz has never
heard of are usually there, with the catalogue number and pressing notes that
make one copy different from another.

Search needs the token; Discogs asks for a descriptive User-Agent and rate
limits to 60 requests a minute, which a manual scan never approaches.
"""

import re

import httpx

from app.config import settings

API = "https://api.discogs.com"
UA = "your-loot/1.0 (+https://github.com/Bokicksit/Your-Loot)"


def _format(parts: list[str], qty: int = 1) -> str | None:
    """Map Discogs' format words onto the options the add form offers."""
    joined = " ".join(parts).lower()
    if "cassette" in joined:
        return "Cassette"
    if "vinyl" in joined:
        if "box set" in joined:
            return "Vinyl box set"
        size = '7"' if '7"' in joined else '10"' if '10"' in joined else '12"'
        # "2×LP" in the descriptions means the same thing as qty 2
        m = re.search(r"(\d+)\s*[x×]\s*lp", joined)
        n = max(qty, int(m.group(1)) if m else 1)
        return f'{n}x{size} Vinyl' if n > 1 else f'{size} Vinyl'
    if re.search(r"\bcd\b", joined):
        return "CD"
    if "box set" in joined:
        return "Vinyl box set"
    return parts[0] if parts else None


def _split_title(text: str) -> tuple[str | None, str | None]:
    """Search results read "Artist - Title"; split on the first dash only, so
    an album with a dash in its name survives."""
    if " - " in text:
        artist, title = text.split(" - ", 1)
        return artist.strip() or None, title.strip() or None
    return None, text.strip() or None


class DiscogsClient:
    def __init__(self):
        self.token = settings.discogs_token

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _get(self, path: str, params: dict) -> dict:
        r = httpx.get(
            f"{API}{path}",
            params=params,
            headers={
                "Authorization": f"Discogs token={self.token}",
                "User-Agent": UA,
                "Accept": "application/json",
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def tracklist(self, release_id: int | str) -> str | None:
        """The running order for one pressing, one track to a line.

        Per pressing rather than per album on purpose: a reissue drops a track,
        a single-disc edit runs them in a different order, and a 12" lists
        sides. That is the level this module already tracks records at.

        Positions are kept ("A1", "B2") because on a record they are where the
        track physically is, not just its number. Durations are kept when
        Discogs has them and simply left off when it doesn't.
        """
        if not self.configured or not release_id:
            return None
        try:
            data = self._get(f"/releases/{release_id}", {})
        except httpx.HTTPError:
            return None  # a missing tracklist is not worth failing an add over

        lines = []
        for t in data.get("tracklist") or []:
            # headings ("Side A") carry no track and would read as a blank row
            if t.get("type_") not in (None, "track"):
                continue
            title = (t.get("title") or "").strip()
            if not title:
                continue
            pos = (t.get("position") or "").strip()
            dur = (t.get("duration") or "").strip()
            lines.append(" · ".join(p for p in (pos, title, dur) if p))
        return "\n".join(lines) or None

    def _summarise(self, hit: dict) -> dict:
        artist, title = _split_title(hit.get("title") or "")
        fmt_parts = [p for p in (hit.get("format") or []) if isinstance(p, str)]
        labels = [l for l in (hit.get("label") or []) if isinstance(l, str)]
        year = hit.get("year")
        fmt = _format(fmt_parts)
        return {
            "mbid": None,  # not a MusicBrainz id; kept so the UI keys line up
            "discogs_id": hit.get("id"),
            "title": title,
            "artist": artist,
            "label": labels[0] if labels else None,
            "catalog_number": hit.get("catno") or None,
            "format": fmt,
            "speed": "45" if fmt and fmt.startswith('7"') else "33⅓",
            # the descriptions that distinguish one pressing from another
            "pressing": ", ".join(
                p for p in fmt_parts
                if p.lower() not in {"vinyl", "lp", "album", "cd", "cassette"}
            ) or None,
            # Discogs files a release under several at once; the first is the
            # one it leads with, and the one a crate divider would say
            "genre": next((g for g in (hit.get("genre") or []) if isinstance(g, str)), None),
            "release_year": int(year) if str(year).isdigit() else None,
            "country": hit.get("country") or None,
            "barcode": None,  # the caller already knows what was scanned
            "track_count": None,
            "image_url": hit.get("cover_image") or hit.get("thumb") or None,
            "source": "discogs",
        }

    def by_barcode(self, barcode: str, limit: int = 10) -> list[dict]:
        digits = "".join(ch for ch in barcode if ch.isdigit())
        if not digits:
            return []
        # Discogs stores barcodes as printed — "0 81227 89224 1" — so if the
        # bare digits miss, try it spaced the way a UPC-A appears on a sleeve
        attempts = [digits]
        if len(digits) == 12:
            attempts.append(f"{digits[0]} {digits[1:6]} {digits[6:11]} {digits[11]}")
        for q in attempts:
            data = self._get(
                "/database/search",
                {"barcode": q, "type": "release", "per_page": limit},
            )
            hits = data.get("results") or []
            if hits:
                return [self._summarise(h) for h in hits[:limit]]
        return []

    def search(self, query: str | None = None, artist: str | None = None,
               limit: int = 10) -> list[dict]:
        params = {"type": "release", "per_page": limit}
        if (artist or "").strip():
            params["artist"] = artist.strip()
        if (query or "").strip():
            params["release_title"] = query.strip()
        if len(params) == 2:
            return []
        data = self._get("/database/search", params)
        return [self._summarise(h) for h in (data.get("results") or [])[:limit]]


discogs_client = DiscogsClient()
