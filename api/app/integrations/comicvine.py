"""Comic Vine client — issue metadata.

Free API key from a Comic Vine account: https://comicvine.gamespot.com/api/
Set it as COMICVINE_API_KEY.

Comic Vine blocks requests without a real User-Agent, so one is always sent.
Rate limit is 200 requests/hour per key, which a manual search never
approaches.

The GCD (Grand Comics Database) was the other free option and needs no key at
all, but its API silently ignores search filters and has no issue-list
endpoint, so it can't answer "find me this issue".
"""

import httpx

from app.config import settings

API = "https://comicvine.gamespot.com/api"
UA = {"User-Agent": "your-loot/1.0 (self-hosted collection tracker)"}


def _year(value: str | None) -> int | None:
    return int(value[:4]) if value and value[:4].isdigit() else None


class ComicVineClient:
    def __init__(self):
        self.api_key = settings.comicvine_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict) -> dict:
        r = httpx.get(
            f"{API}{path}",
            params={"api_key": self.api_key, "format": "json", **params},
            headers=UA,
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    def _summarise(self, issue: dict) -> dict:
        volume = issue.get("volume") or {}
        image = issue.get("image") or {}
        number = issue.get("issue_number")
        series = volume.get("name")
        # Comic Vine's `name` is the story title and is often absent; the
        # collection wants "Series #12" on the shelf either way
        title = " ".join(
            p for p in [series, f"#{number}" if number else None] if p
        ) or issue.get("name") or "Untitled issue"
        return {
            "comicvine_id": issue.get("id"),
            "title": title,
            "story_title": issue.get("name") or None,
            "series": series,
            "issue_number": number,
            "cover_year": _year(issue.get("cover_date")),
            "volume_year": _year((volume.get("start_year") or "")),
            "image_url": image.get("medium_url") or image.get("original_url"),
            "blurb": (issue.get("deck") or "").strip() or None,
        }

    def search(self, query: str, limit: int = 20) -> list[dict]:
        if not (query or "").strip():
            return []
        data = self._get(
            "/search/",
            {"resources": "issue", "query": query.strip(), "limit": limit},
        )
        return [self._summarise(i) for i in (data.get("results") or [])[:limit]]


comicvine_client = ComicVineClient()
