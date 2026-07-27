"""IGDB client — auth via Twitch OAuth client-credentials.

Credentials come from IGDB_CLIENT_ID / IGDB_CLIENT_SECRET (a Twitch dev app,
https://api-docs.igdb.com/#account-creation). The app-access token is cached
in-process and refreshed just before expiry.
"""

import time
from datetime import datetime, timezone

import httpx

from app.config import settings

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_URL = "https://api.igdb.com/v4"


class IGDBClient:
    def __init__(self):
        self.client_id = settings.igdb_client_id
        self.client_secret = settings.igdb_client_secret
        self._token: str | None = None
        self._expires_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        if self._token is None or time.time() > self._expires_at - 60:
            resp = httpx.post(TOKEN_URL, params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._expires_at = time.time() + data.get("expires_in", 3600)
        return self._token

    def search_games(self, query: str, limit: int = 10) -> list[dict]:
        # IGDB queries use their "Apicalypse" language in the POST body
        q = query.replace('"', "")
        body = (
            f'search "{q}"; '
            "fields name,first_release_date,platforms.name,cover.url,"
            "summary,genres.name,involved_companies.company.name,"
            "involved_companies.developer,involved_companies.publisher; "
            f"limit {limit};"
        )
        resp = httpx.post(
            f"{API_URL}/games",
            content=body,
            headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self._get_token()}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if resp.status_code == 401:  # token revoked early — refresh once
            self._token = None
            resp = httpx.post(
                f"{API_URL}/games",
                content=body,
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {self._get_token()}",
                    "Accept": "application/json",
                },
                timeout=15,
            )
        resp.raise_for_status()

        results = []
        for g in resp.json():
            cover = (g.get("cover") or {}).get("url")
            if cover:
                # IGDB returns protocol-relative thumb URLs; t_cover_big = box art
                cover = "https:" + cover.replace("t_thumb", "t_cover_big")
            year = None
            if g.get("first_release_date"):
                year = datetime.fromtimestamp(
                    g["first_release_date"], tz=timezone.utc
                ).year
            companies = g.get("involved_companies") or []
            results.append({
                "igdb_id": g["id"],
                "title": g["name"],
                "year": year,
                "platforms": [p["name"] for p in g.get("platforms", [])],
                "cover_url": cover,
                "summary": g.get("summary"),
                "genres": [x["name"] for x in (g.get("genres") or [])][:4],
                "developer": next(
                    (c["company"]["name"] for c in companies if c.get("developer")),
                    None,
                ),
                "publisher": next(
                    (c["company"]["name"] for c in companies if c.get("publisher")),
                    None,
                ),
            })
        return results


igdb_client = IGDBClient()
