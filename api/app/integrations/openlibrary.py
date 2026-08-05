"""Open Library client — free, no API key, open data.

Two lookups: by ISBN (which is literally the barcode on the back of the
book, so a scan resolves in one call) and by title/author text search.
"""

import httpx

API = "https://openlibrary.org"
COVER = "https://covers.openlibrary.org/b/id/{}-M.jpg"
UA = {"User-Agent": "your-loot/1.0 (self-hosted collection tracker)"}


def _year(text: str | None) -> int | None:
    """Open Library dates are free text: "December 27, 2017", "1998", ..."""
    import re

    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", text or "")
    return int(m.group(1)) if m else None


class OpenLibraryClient:
    def by_isbn(self, isbn: str) -> dict | None:
        code = "".join(ch for ch in isbn if ch.isalnum())
        r = httpx.get(
            f"{API}/api/books",
            params={"bibkeys": f"ISBN:{code}", "format": "json", "jscmd": "data"},
            headers=UA,
            timeout=20,
            follow_redirects=True,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        d = next(iter(data.values()))
        return {
            "title": d.get("title"),
            "author": ", ".join(a["name"] for a in d.get("authors", [])) or None,
            "publisher": ", ".join(p["name"] for p in d.get("publishers", [])) or None,
            "isbn": code,
            "publish_year": _year(d.get("publish_date")),
            "page_count": d.get("number_of_pages"),
            "image_url": (d.get("cover") or {}).get("medium"),
            "olid": (d.get("key") or "").strip("/").split("/")[-1] or None,
        }

    def search(self, query: str, limit: int = 20) -> list[dict]:
        r = httpx.get(
            f"{API}/search.json",
            params={"q": query.strip(), "limit": limit,
                    "fields": "key,title,author_name,first_publish_year,"
                              "cover_i,publisher,isbn,number_of_pages_median"},
            headers=UA,
            timeout=25,
            follow_redirects=True,
        )
        r.raise_for_status()
        out = []
        for d in r.json().get("docs", [])[:limit]:
            isbns = d.get("isbn") or []
            out.append({
                "olid": (d.get("key") or "").strip("/").split("/")[-1],
                "title": d.get("title"),
                "author": ", ".join((d.get("author_name") or [])[:2]) or None,
                "publisher": (d.get("publisher") or [None])[0],
                "publish_year": d.get("first_publish_year"),
                "page_count": d.get("number_of_pages_median"),
                # prefer a 13-digit ISBN when the work lists several
                "isbn": next((i for i in isbns if len(i) == 13), isbns[0] if isbns else None),
                "image_url": COVER.format(d["cover_i"]) if d.get("cover_i") else None,
            })
        return out


openlibrary_client = OpenLibraryClient()
