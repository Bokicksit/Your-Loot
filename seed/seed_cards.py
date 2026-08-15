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
from collections import Counter, defaultdict
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# allow running from anywhere; the api package lives at /app in the container
sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from sqlalchemy import func, select  # noqa: E402
from app.card_art import settled  # noqa: E402
from app.cards_util import classify_layer, derive_variant  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CardAttrs, CollectionItem, Module  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"
DUMP_URL = "https://codeload.github.com/PokemonTCG/pokemon-tcg-data/tar.gz/refs/heads/master"


def build_dex_map(cards_dir: Path) -> dict[str, tuple[int, int]]:
    """name -> (dex number its printings agree on, how many back it).

    The upstream dump gets dex numbers wrong two ways, and a vote across every
    printing repairs both without a hand-kept list:

    * wrong — Black Bolt's Klinklang is tagged 599, which is Klink, filing it
      under the wrong Pokédex slot;
    * missing — Prismatic Evolutions ships Scream Tail and Flutter Mane with
      no number at all, which keeps them out of the Pokédex entirely. Their
      other printings carry one.

    The hit count comes back with the number because how much evidence is
    needed depends on which of the two is being fixed — see seed_file.
    """
    tally: dict[str, Counter] = defaultdict(Counter)
    for path in sorted(cards_dir.glob("*.json")):
        try:
            for card in json.loads(path.read_text(encoding="utf-8")):
                nums = card.get("nationalPokedexNumbers") or []
                if len(nums) == 1:  # unambiguous cards are the evidence
                    tally[card["name"]][nums[0]] += 1
        except (json.JSONDecodeError, OSError):
            continue
    return {name: counts.most_common(1)[0] for name, counts in tally.items()}


def seed_file(db, cards_path: Path, sets_by_id: dict, dex_map: dict | None = None):
    set_code = cards_path.stem  # pokemon-tcg-data names files <set_id>.json
    set_meta = sets_by_id.get(set_code, {})
    set_name = set_meta.get("name", set_code)
    set_total = set_meta.get("printedTotal")
    release = set_meta.get("releaseDate") or ""  # "1999/01/09"
    set_year = int(release[:4]) if release[:4].isdigit() else None
    set_abbr = set_meta.get("ptcgoCode")  # printed code on modern cards (MEW, JTG)
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    created = updated = fixed = filled = 0
    for card in cards:
        dex_nums = card.get("nationalPokedexNumbers") or []
        dex = dex_nums[0] if dex_nums else None
        # Defer to what this Pokémon's other printings say, but demand more
        # evidence to overturn a number than to supply a missing one. Rewriting
        # a stated number on one card's say-so could move a correctly-filed
        # card into the wrong slot; filling a blank can only improve on a card
        # the Pokédex can't accept at all. New species are exactly the case
        # with a single printing to go on.
        agreed, backers = (dex_map or {}).get(card["name"], (None, 0))
        if agreed is not None and agreed != dex:
            if dex is None:
                dex = agreed
                filled += 1
            elif backers > 1:
                dex = agreed
                fixed += 1
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
        # Never clobber a photograph the collector took, nor a card already
        # moved onto TCGdex's asset host — a weekly refresh that quietly put
        # every picture back on somebody else's CDN would undo the whole
        # point of backfill_art.py. See app/card_art.py.
        if not settled(item.image_url):
            item.image_url = (card.get("images") or {}).get("small")
        a = item.card_attrs
        a.set_code = set_code
        a.set_name = set_name
        a.set_total = set_total
        a.set_year = set_year
        a.set_abbr = set_abbr
        a.card_number = card.get("number")
        a.rarity = card.get("rarity")
        a.national_dex_no = dex
        a.variant = derive_variant(card.get("rarity"))
        a.layer = classify_layer(card.get("rarity"))

    db.commit()
    return created, updated, fixed, filled


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
    p.add_argument("--check-empty", action="store_true",
                   help="exit 0 if the card catalog is empty (for first-run seeding)")
    args = p.parse_args()

    if args.check_empty:
        db = SessionLocal()
        try:
            n = db.scalar(
                select(func.count()).select_from(CollectionItem).where(
                    CollectionItem.module == Module.cards.value
                )
            )
        finally:
            db.close()
        print(f"cards in catalog: {n}")
        sys.exit(0 if not n else 1)

    with tempfile.TemporaryDirectory() as tmp:
        cards_dir, sets_file = (
            download_dump(Path(tmp)) if args.download
            else (args.cards_dir, args.sets_file)
        )
        sets = json.loads(sets_file.read_text(encoding="utf-8"))
        sets_by_id = {s["id"]: s for s in sets}

        dex_map = build_dex_map(cards_dir)

        db = SessionLocal()
        total_c = total_u = total_f = total_n = 0
        try:
            files = sorted(cards_dir.glob("*.json"))
            for i, cards_path in enumerate(files, 1):
                c, u, f, n = seed_file(db, cards_path, sets_by_id, dex_map)
                total_c += c
                total_u += u
                total_f += f
                total_n += n
                if args.download:  # progress for the big run
                    print(f"  [{i}/{len(files)}] {cards_path.stem}: +{c} ~{u}")
        finally:
            db.close()
        print(
            f"Done: {total_c} created, {total_u} updated, "
            f"{total_f} dex numbers corrected, {total_n} filled in"
        )


if __name__ == "__main__":
    main()
