"""Seed the amiibo catalogue from the open amiibo database.

    docker compose exec api python /seed/seed_amiibo.py

All 932 figures, cards, yarns and bands, from the AmiiboAPI project's openly
licensed database — the same move as the card catalogue: the whole product
line lives in the shared catalogue, so adding one is picking it, and no
external API is asked at add time.

Idempotent: rows are matched on the head+tail hex id Nintendo burned into
the figure (source="amiibo", external_id=that id), so a re-run after a new
wave ships adds the new figures and touches nothing anybody owns. Titles are
"Character (Series)" only where the same character appears in several
series, because most of the time the character's name alone is the name.

Images stay on the database project's own host — they published them for
exactly this use, and the repo is CDN-backed.
"""

import json
import sys
import urllib.request

sys.path.insert(0, "/app")

from app.db import SessionLocal  # noqa: E402
from app.models import AmiiboAttrs, CollectionItem, Module  # noqa: E402

DB_URL = "https://raw.githubusercontent.com/N3evin/AmiiboAPI/master/database/amiibo.json"
IMG_URL = "https://raw.githubusercontent.com/N3evin/AmiiboAPI/master/images/icon_{}-{}.png"


def fetch() -> dict:
    req = urllib.request.Request(DB_URL, headers={"User-Agent": "your-loot-seed/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> None:
    data = fetch()
    amiibos = data["amiibos"]
    series = {k.lower(): v for k, v in data["amiibo_series"].items()}
    chars = {k.lower(): v for k, v in data["characters"].items()}
    games = {k.lower(): v for k, v in data["game_series"].items()}
    types = {k.lower(): v for k, v in data["types"].items()}

    db = SessionLocal()
    have = {
        i.external_id: i
        for i in db.query(CollectionItem)
        .filter(CollectionItem.module == Module.amiibo.value,
                CollectionItem.source == "amiibo")
        .all()
    }

    # how many figures share a name, so only the ambiguous get a suffix
    names: dict[str, int] = {}
    for key, a in amiibos.items():
        names[a["name"]] = names.get(a["name"], 0) + 1

    added = updated = 0
    for key, a in amiibos.items():
        # 0x + 16 hex digits: head (8) + tail (8). The id encodes the whole
        # identity, in zero-padded hex keys the lookup tables use directly:
        # character = head[0:4], game series = head[0:3], type = head[6:8],
        # amiibo series = tail[4:6]. Verified against all 932 entries with
        # zero misses before this was written down.
        hexid = key.lower()
        head, tail = hexid[2:10], hexid[10:18]
        character = chars.get("0x" + head[0:4])
        game = games.get("0x" + head[0:3])
        figure_type = types.get("0x" + head[6:8])
        ser = series.get("0x" + tail[4:6])

        rel = a.get("release") or {}
        na = rel.get("na")
        year = None
        for region in ("na", "eu", "jp", "au"):
            d = rel.get(region)
            if d:
                year = int(d[:4])
                break

        title = a["name"]
        if names[title] > 1 and ser:
            title = f"{title} ({ser})"

        row = have.get(hexid)
        if row is None:
            item = CollectionItem(
                module=Module.amiibo.value,
                source="amiibo",
                external_id=hexid,
                title=title,
                image_url=IMG_URL.format(head, tail),
                amiibo_attrs=AmiiboAttrs(
                    amiibo_id=hexid,
                    character=character,
                    amiibo_series=ser,
                    game_series=game,
                    figure_type=figure_type,
                    release_year=year,
                    release_na=na,
                ),
            )
            db.add(item)
            added += 1
        else:
            at = row.amiibo_attrs
            changed = False
            for field, value in (
                ("character", character), ("amiibo_series", ser),
                ("game_series", game), ("figure_type", figure_type),
                ("release_year", year), ("release_na", na),
            ):
                if getattr(at, field) != value and value is not None:
                    setattr(at, field, value)
                    changed = True
            if row.title != title:
                row.title = title
                changed = True
            if changed:
                updated += 1
    db.commit()
    total = db.query(CollectionItem).filter(
        CollectionItem.module == Module.amiibo.value
    ).count()
    print(f"amiibo: {added} added, {updated} updated, {total} in the catalogue")
    db.close()


if __name__ == "__main__":
    main()
