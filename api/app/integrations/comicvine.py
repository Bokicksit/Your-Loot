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
        out = [self._summarise(i) for i in (data.get("results") or [])]
        if volume_year:
            # stable, so the runs from the year asked for float up and
            # everything else keeps Comic Vine's own ordering underneath
            out.sort(key=lambda r: r["volume_year"] != volume_year)
        return out[:limit]

    def volumes(self, name: str, limit: int = 100) -> list[dict]:
        data = self._get(
            "/volumes/",
            {
                "filter": f"name:{name.strip()}",
                "limit": limit,
                "field_list": "id,name,start_year,publisher,count_of_issues",
            },
        )
        return data.get("results") or []

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
        # the name filter matches loosely ("Guardians of the Galaxy Annual"),
        # so prefer the runs actually called what was asked for
        want = series.strip().lower()
        exact = [v for v in vols if (v.get("name") or "").strip().lower() == want]
        if exact:
            vols = exact
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
