"""TMDB client stub (phase 2).

TMDB provides base movie metadata (title, year, poster). Physical-edition
fields (format/edition/region code) are always manual entry — TMDB doesn't
know about steelbooks. API key comes from TMDB_API_KEY env var.
"""

import httpx

from app.config import settings

API_URL = "https://api.themoviedb.org/3"


class TMDBClient:
    def __init__(self):
        self.api_key = settings.tmdb_api_key

    def search_movies(self, query: str) -> list[dict]:
        # Phase 2: GET /search/movie?query=...&api_key=...
        # then map poster_path -> https://image.tmdb.org/t/p/w342{poster_path}
        raise NotImplementedError("movies module is phase 2")
