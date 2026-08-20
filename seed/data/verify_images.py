"""Check every image in consoles-na.json exists on Commons and is free.

The dataset's facts are hand-compiled; its images are Wikimedia Commons
filenames, and a filename is a guess until Commons has confirmed it. Two
things are checked, because both are part of the dataset's contract:

  * the file exists — a wrong filename becomes a null image, never a
    broken frame
  * the licence is public domain / CC0 — the app hotlinks these with no
    attribution UI, so a CC-BY photo is as unusable as a 404

Checks go through the API in batches of 50 (single HEADs against
Special:FilePath get rate-limited into useless 429s).

    python verify_images.py         # report
    python verify_images.py --fix   # null the misses in place
"""

import json
import sys
import urllib.parse
import urllib.request

UA = "your-loot-dataset-check/1.0 (+https://yourloot.app)"
API = "https://commons.wikimedia.org/w/api.php"
FREE = ("public domain", "cc0", "pd")


def licence_batch(names: list[str]) -> dict[str, str | None]:
    """name -> licence short-name, or None if the file does not exist."""
    out: dict[str, str | None] = {}
    uniq = list(dict.fromkeys(names))
    for i in range(0, len(uniq), 50):
        chunk = uniq[i : i + 50]
        qs = urllib.parse.urlencode({
            "action": "query", "format": "json",
            "titles": "|".join(f"File:{n}" for n in chunk),
            "prop": "imageinfo", "iiprop": "extmetadata",
            "iiextmetadatafilter": "LicenseShortName",
        })
        req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        norm = {n["to"]: n["from"] for n in d.get("query", {}).get("normalized", [])}
        for page in d.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            asked = norm.get(title, title).removeprefix("File:")
            if "missing" in page or "imageinfo" not in page:
                out[asked] = None
                continue
            meta = page["imageinfo"][0].get("extmetadata", {})
            out[asked] = meta.get("LicenseShortName", {}).get("value", "unknown")
    return out


def main() -> None:
    with open("consoles-na.json", encoding="utf-8") as f:
        data = json.load(f)

    named = [
        (e, urllib.parse.unquote(e["image"].rsplit("/", 1)[-1]))
        for e in data["entries"] if e["image"]
    ]
    lic = licence_batch([n for _, n in named])

    misses = []
    for e, n in named:
        l = lic.get(n)
        if l is None:
            misses.append((e["slug"], "missing", n))
        elif not any(t in l.lower() for t in FREE):
            misses.append((e["slug"], l, n))

    print(f"{len(named)} images checked, {len(misses)} unusable")
    for slug, why, name in misses:
        print(f"  {slug}  [{why}]  ({name})")

    if misses and "--fix" in sys.argv:
        bad = {m[0] for m in misses}
        for e in data["entries"]:
            if e["slug"] in bad:
                e["image"] = None
        with open("consoles-na.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        print(f"nulled {len(bad)} — the gaps are honest now")


if __name__ == "__main__":
    main()
