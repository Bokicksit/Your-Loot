"""Seed cards from a PokemonTCG/pokemon-tcg-data JSON dump (offline, no API).

Usage (inside the api container, where /seed is baked in):
    python /seed/seed_cards.py                # committed sample set only
    python /seed/seed_cards.py --download     # fetch + seed the FULL dump
    python /seed/seed_cards.py --cards-dir X --sets-file Y   # local dump

Re-running is safe: rows upsert on (source='ptcg', external_id=card id) and
owned/wanted records are never touched.
"""

import argparse
import io
import json
import re
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# allow running from anywhere; the api package lives at /app in the container
sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from sqlalchemy import select  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CardAttrs, CollectionItem, Module  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"
DUMP_URL = "https://codeload.github.com/PokemonTCG/pokemon-tcg-data/tar.gz/refs/heads/master"


def derive_variant(rarity: str | None) -> str:
    r = (rarity or "").lower()
    if "full art" in r or "ultra" in r:
        return "full-art"
    if "holo" in r:
        return "holo"
    return "normal"


def classify_layer(rarity: str | None) -> int:
    """Binder layer by card *style*, era-agnostic (per Bo's binder rules):
    3 = IR / SIR / alt-illustration styles
    2 = full-art (SV ex Ultra Rare, V/VMAX/VSTAR/GX/EX full arts, rainbows)
    1 = everything else: commons/uncommons/holos, regular ex (Double Rare),
        vintage cards, and gold Hyper Rares / Secrets (Bo files golds as basic)
    """
    r = (rarity or "").lower()
    if "illustration" in r or "trainer gallery" in r:
        return 3
    if (
        "ultra" in r
        or "full art" in r
        or "rainbow" in r
        or re.search(r"holo (v|vmax|vstar|gx|ex|lv\.x)\b", r)
    ):
        return 2
    return 1


def seed_file(db, cards_path: Path, sets_by_id: dict):
    set_code = cards_path.stem  # pokemon-tcg-data names files <set_id>.json
    set_meta = sets_by_id.get(set_code, {})
    set_name = set_meta.get("name", set_code)
    set_total = set_meta.get("printedTotal")
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
        a.set_total = set_total
        a.card_number = card.get("number")
        a.rarity = card.get("rarity")
        a.national_dex_no = dex_nums[0] if dex_nums else None
        a.variant = derive_variant(card.get("rarity"))
        a.layer = classify_layer(card.get("rarity"))

    db.commit()
    return created, updated


def download_dump(dest: Path) -> tuple[Path, Path]:
    """Fetch the full dump tarball (no git needed) -> (cards_dir, sets_file)."""
    print(f"Downloading {DUMP_URL} …")
    req = urllib.request.Request(DUMP_URL, headers={"User-Agent": "your-loot-seed"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    print(f"  {len(data) // (1024 * 1024)} MB — extracting…")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    root = next(dest.glob("pokemon-tcg-data-*"))
    return root / "cards" / "en", root / "sets" / "en.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--download", action="store_true",
                   help="fetch and seed the full pokemon-tcg-data dump")
    p.add_argument("--cards-dir", type=Path, default=SAMPLE_DIR / "cards",
                   help="directory of <set_id>.json card files")
    p.add_argument("--sets-file", type=Path, default=SAMPLE_DIR / "sets.json")
    args = p.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        cards_dir, sets_file = (
            download_dump(Path(tmp)) if args.download
            else (args.cards_dir, args.sets_file)
        )
        sets = json.loads(sets_file.read_text(encoding="utf-8"))
        sets_by_id = {s["id"]: s for s in sets}

        db = SessionLocal()
        total_c = total_u = 0
        try:
            files = sorted(cards_dir.glob("*.json"))
            for i, cards_path in enumerate(files, 1):
                c, u = seed_file(db, cards_path, sets_by_id)
                total_c += c
                total_u += u
                if args.download:  # progress for the big run
                    print(f"  [{i}/{len(files)}] {cards_path.stem}: +{c} ~{u}")
        finally:
            db.close()
        print(f"Done: {total_c} created, {total_u} updated")


if __name__ == "__main__":
    main()
