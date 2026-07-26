"""TMDB client — base movie metadata (title, year, poster).

Physical-edition fields (format/edition/region) are always manual entry;
TMDB doesn't know about steelbooks. API key comes from TMDB_API_KEY
(free: https://www.themoviedb.org/settings/api, v3 key).
"""

import httpx

from app.config import settings

API_URL = "https://api.themoviedb.org/3"
IMG_URL = "https://image.tmdb.org/t/p/w342"  # poster size that fits our tiles


class TMDBClient:
    def __init__(self):
        self.api_key = settings.tmdb_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search_movies(self, query: str, limit: int = 10) -> list[dict]:
        resp = httpx.get(
            f"{API_URL}/search/movie",
            params={"query": query, "api_key": self.api_key, "include_adult": "false"},
            timeout=15,
        )
        resp.raise_for_status()
        results = []
        for m in resp.json().get("results", [])[:limit]:
            results.append({
                "tmdb_id": m["id"],
                "title": m.get("title") or m.get("original_title") or "?",
                "year": (m.get("release_date") or "")[:4] or None,
                "poster_url": IMG_URL + m["poster_path"] if m.get("poster_path") else None,
            })
        return results


tmdb_client = TMDBClient()
