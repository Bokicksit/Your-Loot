"""Seed cards from a PokemonTCG/pokemon-tcg-data JSON dump (offline, no API).

Usage (inside the api container, where /seed is baked in):
    python /seed/seed_cards.py                          # committed sample set
    python /seed/seed_cards.py --cards-dir /tmp/ptcg/cards/en \
                               --sets-file /tmp/ptcg/sets/en.json

Re-running is safe: rows upsert on (source='ptcg', external_id=card id).
"""

import argparse
import json
import sys
from pathlib import Path

# allow running from anywhere; the api package lives at /app in the container
sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from sqlalchemy import select  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CardAttrs, CollectionItem, Module  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"


def derive_variant(rarity: str | None) -> str:
    """Best-effort variant from rarity text. The dump doesn't model variants
    directly; reverse-holo rows can be added manually or in a later pass."""
    r = (rarity or "").lower()
    if "full art" in r or "ultra" in r:
        return "full-art"
    if "holo" in r:
        return "holo"
    return "normal"


def seed_file(db, cards_path: Path, sets_by_id: dict):
    set_code = cards_path.stem  # pokemon-tcg-data names files <set_id>.json
    set_name = sets_by_id.get(set_code, {}).get("name", set_code)
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    created = updated = 0
    for card in cards:
        dex_nums = card.get("nationalPokedexNumbers") or []
        item = db.scalar(
            select(CollectionItem).where(
                CollectionItem.source == "ptcg",
                CollectionItem.external_id == card["id"],
            )
        )
        if item is None:
            item = CollectionItem(module=Module.cards.value, source="ptcg",
                                  external_id=card["id"], card_attrs=CardAttrs())
            db.add(item)
            created += 1
        else:
            updated += 1

        item.title = card["name"]
        item.image_url = (card.get("images") or {}).get("small")
        a = item.card_attrs
        a.set_code = set_code
        a.set_name = set_name
        a.card_number = card.get("number")
        a.rarity = card.get("rarity")
        a.national_dex_no = dex_nums[0] if dex_nums else None
        a.variant = derive_variant(card.get("rarity"))

    db.commit()
    print(f"{set_code}: {created} created, {updated} updated")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cards-dir", type=Path, default=SAMPLE_DIR / "cards",
                   help="directory of <set_id>.json card files")
    p.add_argument("--sets-file", type=Path, default=SAMPLE_DIR / "sets.json")
    args = p.parse_args()

    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))
    sets_by_id = {s["id"]: s for s in sets}

    db = SessionLocal()
    try:
        for cards_path in sorted(args.cards_dir.glob("*.json")):
            seed_file(db, cards_path, sets_by_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
