"""Rebrickable client — LEGO set metadata.

Free API key from a Rebrickable account: https://rebrickable.com/users/_/settings/#api
(Account → Settings → API). Set it as REBRICKABLE_API_KEY.

Rebrickable knows sets, not boxes: it has the set number, name, year, theme and
piece count, but nothing about what a second-hand box is missing — that's the
per-copy completeness the app tracks itself.
"""

import re

import httpx

from app.config import settings

API = "https://rebrickable.com/api/v3/lego"

# How many results to rank before handing back a page of them. One request
# either way; Rebrickable's own order is by set number, so a small page is a
# near-random slice of what matched.
POOL = 100

# Anything that is not a letter or a digit is a gap between words. Used to
# ask whether a search term appears as a word rather than inside one —
# spelled as a split rather than a pattern built around the term, because
# a term is whatever somebody typed and does not belong in a regex.
WORDS = re.compile(r"[^a-z0-9]+")


def _relevance(name: str, term: str) -> int:
    """How squarely a set's name answers what was typed. Lower is better."""
    n = (name or "").lower()
    q = term.lower().strip()
    if n == q:
        return 0                                   # "Titanic"
    if n.startswith(q):
        return 1                                   # "Bonsai Tree" for "bonsai"
    if f" {q} " in " " + WORDS.sub(" ", n) + " ":
        return 2                                   # the words, somewhere in it
    if q in n:
        return 3                                   # buried inside another word
    return 4                                       # matched on something else


def _rank(s: dict, term: str) -> tuple:
    """The order a person would put these in.

    Pieces first, and that is the whole fix. Rebrickable catalogues the LEGO
    video games alongside the sets — seventeen of the thirty-five things
    called "nintendo" are Switch titles with no bricks in them — and a shelf
    of physical sets is not where somebody goes looking for those. They are
    ranked last rather than dropped, because being unfindable is its own bug
    and the catalogue is not ours to censor.

    Then how well the name matches, then size: searching a theme should offer
    the big set before a keyring of it, and the newer one before its
    predecessor.
    """
    parts = s.get("num_parts") or 0
    return (
        0 if parts > 0 else 1,
        _relevance(s.get("name", ""), term),
        -parts,
        -(s.get("year") or 0),
    )


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
        term = query.strip()
        # A wide net, then our own ordering. Rebrickable answers a name search
        # in set-number order, which is no order at all to a person: "nintendo"
        # returns thirty-five things and hands back the twenty whose numbers
        # sort first, and the Nintendo Entertainment System is not among them.
        # Asking for the lot costs one request and lets the sort below decide.
        data = self._get("/sets/", {"search": term, "page_size": POOL})
        ranked = sorted(data.get("results", []), key=lambda s: _rank(s, term))
        return [self._summarise(s) for s in ranked[:limit]]


rebrickable_client = RebrickableClient()
