"""Seed the hardware catalogue from the repo's own console dataset.

Runs automatically on every API start (see entrypoint.sh) — by hand only
when debugging:

    docker compose exec api python /seed/seed_consoles.py

Unlike cards and amiibo this reads no network at all: consoles-na.json is
ours, lives in the repo next to this script, and was verified (existence and
licence of every image) before it was committed. The entries become template
rows in the games module — source="yourloot", external_id=slug — that the
hardware page's catalogue search offers for pick-to-prefill. Nobody owns a
template; picking one prefills the add form and the user's submit creates
their own row, because a console's serial number and whether it still works
belong to the physical unit on their shelf, not to the catalogue.

Idempotent: matched on source+external_id, so a re-run after the dataset
grows adds the new entries and refreshes facts on the rest, touching nothing
anybody owns (owned rows are separate items entirely).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.db import SessionLocal  # noqa: E402
from app.models import CollectionItem, GameAttrs, Module, Platform  # noqa: E402

DATA = Path(__file__).parent / "data" / "consoles-na.json"

# The dataset says "Genesis" the way a collector does; the platforms table
# says "Sega Genesis" the way the initial migration seeded it. This adapter
# keeps the published dataset natural and the database canonical — without
# it, seeding would mint an "SNES" row alongside "Super Nintendo" and the
# platform dropdown would offer both.
CANON = {
    "Dreamcast": "Sega Dreamcast",
    "GameCube": "Nintendo GameCube",
    "Genesis": "Sega Genesis",
    "NES": "Nintendo Entertainment System",
    "PS Vita": "PlayStation Vita",
    "PSP": "PlayStation Portable",
    "SNES": "Super Nintendo",
    "Switch": "Nintendo Switch",
    "Wii": "Nintendo Wii",
    "Wii U": "Nintendo Wii U",
    "Xbox Series X": "Xbox Series X|S",
}


def main() -> None:
    with open(DATA, encoding="utf-8") as f:
        entries = json.load(f)["entries"]

    db = SessionLocal()
    have = {
        i.external_id: i
        for i in db.query(CollectionItem)
        .filter(CollectionItem.module == Module.games.value,
                CollectionItem.source == "yourloot")
        .all()
    }
    platforms = {p.name: p for p in db.query(Platform).all()}

    def platform_for(name: str | None) -> Platform | None:
        if not name:
            return None
        name = CANON.get(name, name)
        if name not in platforms:
            platforms[name] = Platform(name=name)
            db.add(platforms[name])
            db.flush()
        return platforms[name]

    added = updated = 0
    for e in entries:
        plat = platform_for(e["platform"])
        row = have.get(e["slug"])
        if row is None:
            db.add(CollectionItem(
                module=Module.games.value,
                source="yourloot",
                external_id=e["slug"],
                title=e["title"],
                image_url=e["image"],
                game_attrs=GameAttrs(
                    is_hardware=True,
                    hardware_kind=e["kind"],
                    platform_id=plat.id if plat else None,
                    region="NTSC-U",
                    model_number=e["model_number"],
                    release_year=e["release_year"],
                ),
            ))
            added += 1
        else:
            # facts refresh on re-run — a corrected year or a photo that
            # arrived by PR should reach installs that seeded earlier
            row.title = e["title"]
            row.image_url = e["image"]
            a = row.game_attrs
            a.hardware_kind = e["kind"]
            a.platform_id = plat.id if plat else a.platform_id
            a.model_number = e["model_number"]
            a.release_year = e["release_year"]
            updated += 1

    db.commit()
    print(f"hardware catalogue: {added} added, {updated} refreshed, "
          f"{len(entries)} in the dataset")


if __name__ == "__main__":
    main()
