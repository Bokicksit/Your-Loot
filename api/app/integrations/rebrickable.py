"""Rebrickable client — LEGO set metadata.

Free API key from a Rebrickable account: https://rebrickable.com/users/_/settings/#api
(Account → Settings → API). Set it as REBRICKABLE_API_KEY.

Rebrickable knows sets, not boxes: it has the set number, name, year, theme and
piece count, but nothing about what a second-hand box is missing — that's the
per-copy completeness the app tracks itself.
"""

import httpx

from app.config import settings

API = "https://rebrickable.com/api/v3/lego"


class RebrickableClient:
    def __init__(self):
        self.api_key = settings.rebrickable_api_key
        self._themes: dict[int, str] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict) -> dict:
        r = httpx.get(
            f"{API}{path}",
            params=params,
            headers={
                "Authorization": f"key {self.api_key}",
                "User-Agent": "your-loot/1.0",
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def _theme_name(self, theme_id: int | None) -> str | None:
        """Themes are a small fixed list, so fetch it once and keep it — a
        lookup per search result would be a request per row."""
        if theme_id is None:
            return None
        if self._themes is None:
            try:
                data = self._get("/themes/", {"page_size": 1000})
                self._themes = {t["id"]: t["name"] for t in data.get("results", [])}
            except httpx.HTTPError:
                self._themes = {}
        return self._themes.get(theme_id)

    def _summarise(self, s: dict) -> dict:
        return {
            "set_number": s.get("set_num"),
            "title": s.get("name"),
            "release_year": s.get("year"),
            "piece_count": s.get("num_parts"),
            "theme": self._theme_name(s.get("theme_id")),
            "image_url": s.get("set_img_url"),
        }

    def search(self, query: str | None = None, set_number: str | None = None,
               limit: int = 20) -> list[dict]:
        if set_number and set_number.strip():
            # Rebrickable ids carry a variant suffix; "10276" alone won't match
            num = set_number.strip()
            if "-" not in num:
                num = f"{num}-1"
            try:
                return [self._summarise(self._get(f"/sets/{num}/", {}))]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise
        if not (query or "").strip():
            return []
        data = self._get("/sets/", {"search": query.strip(), "page_size": limit})
        return [self._summarise(s) for s in data.get("results", [])[:limit]]


rebrickable_client = RebrickableClient()
