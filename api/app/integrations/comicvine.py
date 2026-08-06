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

import re

import httpx

from app.config import settings

API = "https://comicvine.gamespot.com/api"
UA = {"User-Agent": "your-loot/1.0 (self-hosted collection tracker)"}


def _year(value: str | None) -> int | None:
    return int(value[:4]) if value and value[:4].isdigit() else None


def _key(name: str) -> str:
    """Series names for comparing.

    Case, punctuation and articles all differ between what you type and what
    Comic Vine files it under — "Spider-Man" / "Spider Man", and the original
    run is "The Amazing Spider-Man" however you say it out loud. None of those
    differences mean anything, so all three go.
    """
    s = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    return re.sub(r"\b(the|a|an)\b", " ", s).strip()


class ComicVineClient:
    def __init__(self):
        self.api_key = settings.comicvine_api_key
        # a paged volume search costs up to five requests against a 200/hour
        # budget, and searching the same series twice while you get the issue
        # number right is the normal way to use this
        self._volume_cache: dict[str, list[dict]] = {}

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

    def _summarise(self, issue: dict, volume_years: dict | None = None) -> dict:
        volume = issue.get("volume") or {}
        image = issue.get("image") or {}
        number = issue.get("issue_number")
        series = volume.get("name")
        # /issues/ returns a volume stub with no start_year in it, so when the
        # run was looked up first its year is carried in rather than lost —
        # which run an issue belongs to is the whole point of the search
        vol_year = _year(volume.get("start_year") or "")
        if vol_year is None and volume_years:
            vol_year = volume_years.get(volume.get("id"))
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
            "volume_year": vol_year,
            "image_url": image.get("medium_url") or image.get("original_url"),
            "blurb": (issue.get("deck") or "").strip() or None,
        }

    def search(self, query: str, limit: int = 50, volume_year: int | None = None) -> list[dict]:
        """Full-text across every issue Comic Vine knows. Noisy by nature —
        prefer find() whenever there's a series and an issue number."""
        if not (query or "").strip():
            return []
        data = self._get(
            "/search/",
            {"resources": "issue", "query": query.strip(), "limit": limit},
        )
        raw = data.get("results") or []
        out = [self._summarise(i) for i in raw]
        self._fill_volume_years(out, raw)
        if volume_year:
            # stable, so the runs from the year asked for float up and
            # everything else keeps Comic Vine's own ordering underneath
            out.sort(key=lambda r: r["volume_year"] != volume_year)
        return out[:limit]

    def _fill_volume_years(self, rows: list[dict], raw: list[dict]) -> None:
        """/search/ hands back a volume stub carrying no start year, so every
        result would claim to belong to no run at all — which is the one thing
        that tells six identically titled #1s apart. One batched lookup fills
        them in for the whole page."""
        ids = {(i.get("volume") or {}).get("id") for i in raw}
        ids.discard(None)
        if not ids:
            return
        try:
            data = self._get(
                "/volumes/",
                {
                    "filter": "id:" + "|".join(str(i) for i in sorted(ids)[:100]),
                    "limit": 100,
                    "field_list": "id,start_year",
                },
            )
        except httpx.HTTPError:
            return  # labels are a nicety; the results themselves still stand
        years = {
            v.get("id"): _year(v.get("start_year") or "")
            for v in (data.get("results") or [])
        }
        for row, issue in zip(rows, raw):
            if row["volume_year"] is None:
                row["volume_year"] = years.get((issue.get("volume") or {}).get("id"))

    def volumes(self, name: str, max_pages: int = 5) -> list[dict]:
        """Every run actually called `name`.

        Comic Vine's name filter is a contains-match: "Saga" returns 452
        volumes, most of them "…Saga of…" something, and the one you want is
        nowhere near the first page. So this pages through sorted by name,
        keeping only the runs whose title really is what was asked for, and
        stops as soon as the sort has run past it. Falls back to the loose
        first page when nothing matches exactly, so a near-miss still shows
        something.
        """
        want = _key(name)
        if want in self._volume_cache:
            return self._volume_cache[want]
        exact: list[dict] = []
        loose: list[dict] = []
        offset = 0
        for _ in range(max_pages):
            data = self._get(
                "/volumes/",
                {
                    "filter": f"name:{name.strip()}",
                    "limit": 100,
                    "offset": offset,
                    "sort": "name:asc",
                    "field_list": "id,name,start_year,publisher,count_of_issues",
                },
            )
            page = data.get("results") or []
            if not page:
                break
            if not loose:
                loose = page
            exact.extend(v for v in page if _key(v.get("name") or "") == want)
            offset += len(page)
            if offset >= (data.get("number_of_total_results") or 0):
                break
            # No stopping early on the sort order. Comic Vine sorts on the raw
            # name and files the original run as "The Amazing Spider-Man",
            # which lands under T — long past the A we'd be comparing against,
            # and after three perfectly real "Amazing Spider-Man" runs that
            # would have looked like a good enough reason to stop.
        out = exact or loose
        self._volume_cache[want] = out
        return out

    def find(
        self,
        series: str,
        issue_number: str,
        volume_year: int | None = None,
        limit: int = 40,
    ) -> list[dict]:
        """The exact issue, by way of the run it belongs to.

        /search/ is full text over every issue in the database, so "Guardians
        of the Galaxy 1" buries the 2008 run under every other Guardians issue
        ever printed, and the cap cuts it off long before you reach the one you
        wanted. Volumes are a short, filterable list; once you know which run
        you mean, the issue is one exact lookup.
        """
        # volumes() has already narrowed to runs of exactly this name, so the
        # year is applied to those rather than the other way round — filtering
        # by year first would pick 2008 out of every "…of the Galaxy Annual"
        # in the database and never reach the run itself
        vols = self.volumes(series)
        if not vols:
            return []
        if volume_year:
            same_year = [
                v for v in vols if _year(v.get("start_year") or "") == volume_year
            ]
            # an empty result here means the year is wrong, not that there's
            # nothing to show — fall through to every run of that name
            if same_year:
                vols = same_year
        vols = vols[:20]  # the filter is a URL, not a manifesto
        years = {v.get("id"): _year(v.get("start_year") or "") for v in vols}
        data = self._get(
            "/issues/",
            {
                # Comic Vine ORs repeated values of one field with a pipe
                "filter": "volume:%s,issue_number:%s"
                % ("|".join(str(v.get("id")) for v in vols), issue_number.strip()),
                "limit": limit,
            },
        )
        return [self._summarise(i, years) for i in (data.get("results") or [])[:limit]]


comicvine_client = ComicVineClient()
