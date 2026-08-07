"""Open Library client — free, no API key, open data.

Two lookups: by ISBN (which is literally the barcode on the back of the
book, so a scan resolves in one call) and by title/author text search.

A blurb is a third call, and deliberately not part of either — it hangs off
the *work* rather than the edition, and fetching one per row would mean
twenty requests to draw a page of search results. It's fetched once, for the
book actually chosen.
"""

import re

import httpx

API = "https://openlibrary.org"
COVER = "https://covers.openlibrary.org/b/id/{}-M.jpg"
UA = {"User-Agent": "your-loot/1.0 (self-hosted collection tracker)"}


# Descriptions are contributor-written Markdown, and the longer ones trail
# housekeeping: a horizontal rule, then a source credit or a "contains" list,
# then a block of link definitions. None of that is the book.
_SEPARATOR = re.compile(r"\n\s*[-*_]{4,}\s*\n.*", re.S)
_LINK_DEFS = re.compile(r"^\s*\[[^\]]+\]:\s*\S+\s*$", re.M)
_INLINE_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BLANK_RUN = re.compile(r"\n{3,}")


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = _SEPARATOR.sub("", out)
    out = _LINK_DEFS.sub("", out)
    out = _INLINE_LINK.sub(r"\1", out)  # keep the words, drop the URL
    out = _BLANK_RUN.sub("\n\n", out).strip()
    return out or None


def _year(text: str | None) -> int | None:
    """Open Library dates are free text: "December 27, 2017", "1998", ..."""
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

    def description(self, olid: str) -> str | None:
        """The blurb for a book, or None if Open Library hasn't got one.

        Which it often hasn't — coverage is good for anything well known and
        thin below that, so this is a bonus rather than something to build on.

        A search result is already a work ("OL…W"). A scanned barcode gives an
        *edition* ("OL…M"), which knows the printing, the page count and the
        cover but not the story — that belongs to the work the edition is one
        printing of, one hop away.
        """
        olid = (olid or "").strip()
        if not olid:
            return None
        try:
            key = f"works/{olid}"
            if olid.endswith("M"):
                r = httpx.get(f"{API}/books/{olid}.json", headers=UA, timeout=20,
                              follow_redirects=True)
                r.raise_for_status()
                works = r.json().get("works") or []
                if not works:
                    return None
                key = (works[0].get("key") or "").strip("/")
            r = httpx.get(f"{API}/{key}.json", headers=UA, timeout=20,
                          follow_redirects=True)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None  # a missing blurb is not worth failing an add over

        text = data.get("description")
        if isinstance(text, dict):  # older records wrap it in a typed value
            text = text.get("value")
        return _clean(text)


openlibrary_client = OpenLibraryClient()
