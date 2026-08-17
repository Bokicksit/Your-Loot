"""Seed the Japanese catalogue from TCGdex's cards-database (MIT, offline).

Usage (inside the api container, where /seed is baked in):
    python /seed/seed_cards_ja.py --dry-run    # say what it would import
    python /seed/seed_cards_ja.py --download   # fetch the repo and seed
    python /seed/seed_cards_ja.py --repo DIR   # seed from a copy on disk

Deliberately not part of first-run seeding. A self-hosted install should get
the catalogue it asked for and nothing else, and this doubles it.

Why this source. The English catalogue comes from pokemon-tcg-data, which is
English only — SV1a "Triplet Beat" never had an English printing, so it is
not a translation problem, it is a set the other dump has never heard of.
TCGdex keeps the Asian sets in `data-asia/` of the same MIT repository whose
artwork the cards already point at, so this needs no key, no account and no
terms conversation. That last part is why this collection could be built when
four others could not.

Two things about the data are worth knowing before reading the code.

`data-asia` is Asia, not Japan: the same folder carries Korean, Traditional
Chinese, Thai and Indonesian printings, and plenty of cards there have no
Japanese name at all. About 5,000 of the 18,000 files are somebody else's
language. A card is Japanese here if it has one, and nothing else counts.

The card files are TypeScript rather than JSON, because the repository is
compiled into an API rather than published as a dump. They are regular object
literals and the handful of fields wanted here are scalars, so they are read
by pattern rather than by evaluating somebody else's TypeScript — which would
mean shipping a Node toolchain in this image to import 13,000 files.
"""

import argparse
import io
import re
import sys
import tarfile
import tempfile
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from sqlalchemy import select  # noqa: E402
from app.card_art import settled  # noqa: E402
from app.binder_view import species_names  # noqa: E402
from app.cards_util import classify_layer, derive_variant  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CardAttrs, CollectionItem, Module  # noqa: E402

REPO_URL = "https://codeload.github.com/tcgdex/cards-database/tar.gz/refs/heads/master"
ASSETS = "https://assets.tcgdex.net/ja"
SOURCE = "tcgdex-ja"


# ---------------------------------------------------------------- parsing


def _block(src: str, key: str) -> str | None:
    """The `{...}` following `key:`, brace-matched.

    A plain regex stops at the first closing brace, which on a card with an
    attack inside its name block would return half an object.
    """
    m = re.search(rf"^\s*{key}\s*:\s*\{{", src, re.M)
    if not m:
        return None
    start = src.index("{", m.start())
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    return None


def _str(src: str | None, key: str) -> str | None:
    """A quoted scalar, either quoting style, key quoted or not ('zh-tw')."""
    m = re.search(rf"^\s*'?{key}'?\s*:\s*(?:'([^']*)'|\"([^\"]*)\")", src or "", re.M)
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)


def _int(src: str | None, key: str) -> int | None:
    m = re.search(rf"^\s*'?{key}'?\s*:\s*(\d+)", src or "", re.M)
    return int(m.group(1)) if m else None


def parse_card(src: str) -> dict | None:
    """One card, or None if it is not a Japanese one."""
    name = _str(_block(src, "name"), "ja")
    if not name:
        return None  # Korean, Chinese, Thai — somebody else's catalogue
    dex = re.search(r"^\s*dexId\s*:\s*\[([0-9,\s]*)\]", src, re.M)
    nums = [int(x) for x in dex.group(1).replace(" ", "").split(",") if x] if dex else []
    rarity = _str(src, "rarity")
    return {
        "name": name,
        # TCGdex writes the string "None" where a card has no rarity, which is
        # a value rather than an absence and would otherwise be filed as one.
        "rarity": None if rarity in (None, "None") else rarity,
        "category": _str(src, "category"),
        "illustrator": _str(src, "illustrator"),
        # A card can list two (Mega Evolutions, tag teams); the binder has one
        # slot per species and the first is the one the card is named for.
        "dex": nums[0] if nums else None,
    }


def parse_set(src: str) -> dict:
    counts = _block(src, "cardCount") or ""
    names = _block(src, "name")
    # releaseDate is a date per language on sets that got one, and a plain
    # string on the old ones that were released everywhere at once.
    release = _str(_block(src, "releaseDate"), "ja") or _str(src, "releaseDate") or ""
    return {
        # What the set calls itself, which is not always what its folder is
        # called: the folder "Miscellaneous Promos" holds the set `miscp`.
        "id": _str(src, "id"),
        # English where there is no Japanese name — a set can hold Japanese
        # cards and still be catalogued under an English title.
        "name": _str(names, "ja") or _str(names, "en"),
        "official": _int(counts, "official"),
        "total": _int(counts, "total"),
        "year": int(release[:4]) if release[:4].isdigit() else None,
    }


# ------------------------------------------------------------------- art


def art_url(serie: str, set_id: str, number: str) -> str:
    return f"{ASSETS}/{serie}/{set_id}/{number}/high.png"


def _has_art(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD")
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False


def sets_with_art(probes: list[tuple[str, str, str]]) -> set[str]:
    """Which sets have artwork, asked once per set rather than once per card.

    Two things make this cheap. TCGdex's own card records under-report it —
    every card of M1S came back with no image while all 92 were sitting on the
    asset host — so the records cannot be trusted and the host has to be asked.
    And a set is all or nothing: 237 of 237 on SV8a including the secret rares,
    92 of 92 on M1S, 0 of 102 on the 1996 sets. So one card answers for a set,
    and this is 124 requests rather than 13,000.
    """
    def ask(probe):
        set_id, serie, number = probe
        return set_id, _has_art(art_url(serie, set_id, number))

    with ThreadPoolExecutor(max_workers=8) as ex:
        return {set_id for set_id, ok in ex.map(ask, probes) if ok}


# ---------------------------------------------------------------- seeding


def collect(root: Path) -> tuple[list[dict], dict]:
    """Every Japanese card under data-asia, and the sets they belong to."""
    base = root / "data-asia"
    sets: dict[str, dict] = {}
    cards: list[dict] = []

    for card_file in sorted(base.glob("*/*/*.ts")):
        set_id = card_file.parent.name
        serie = card_file.parent.parent.name
        if set_id not in sets:
            meta_file = card_file.parent.parent / f"{set_id}.ts"
            if not meta_file.exists():
                continue
            meta = parse_set(meta_file.read_text(encoding="utf-8", errors="replace"))
            meta["serie"] = serie
            sets[set_id] = meta

        card = parse_card(card_file.read_text(encoding="utf-8", errors="replace"))
        if card is None:
            continue
        card["set_id"] = set_id
        card["serie"] = serie
        card["number"] = card_file.stem
        cards.append(card)

    # a set nothing Japanese survived in is a Korean or Chinese set
    kept = {c["set_id"] for c in cards}
    return cards, {k: v for k, v in sets.items() if k in kept}


def seed(db, cards: list[dict], sets: dict, illustrated: set[str]) -> Counter:
    n = Counter()
    # What the English catalogue calls each species, asked once. Without it a
    # Japanese card can only be found by typing Japanese, which for almost
    # everybody means it cannot be found at all.
    english = species_names(db)
    for card in cards:
        meta = sets[card["set_id"]]
        code = meta.get("id") or card["set_id"]
        external = f"{code}-{card['number']}"
        item = db.scalar(
            select(CollectionItem).where(
                CollectionItem.source == SOURCE,
                CollectionItem.external_id == external,
            )
        )
        if item is None:
            item = CollectionItem(
                module=Module.cards.value, source=SOURCE,
                external_id=external, card_attrs=CardAttrs(),
            )
            db.add(item)
            n["created"] += 1
        else:
            n["updated"] += 1

        item.title = card["name"]
        # A photograph the collector took outranks the catalogue, always. A
        # set with no artwork keeps a null rather than a URL that 404s: the
        # tile draws its own empty frame for one and a broken image for the
        # other.
        if not settled(item.image_url):
            if card["set_id"] in illustrated:
                item.image_url = art_url(card["serie"], card["set_id"], card["number"])
                n["with_art"] += 1
            else:
                item.image_url = None
                n["no_art"] += 1

        a = item.card_attrs
        a.language = "ja"
        a.set_code = code
        a.set_name = meta.get("name") or code
        a.set_total = meta.get("official") or meta.get("total")
        a.set_year = meta.get("year")
        # The printed code, which on a Japanese card is the set code itself.
        # Null rather than truncated if it is somehow not one: a badge reading
        # "Miscellane" is worse than no badge, and the set name still says it.
        a.set_abbr = code if len(code) <= 10 else None
        a.card_number = card["number"]
        a.rarity = card["rarity"]
        a.national_dex_no = card["dex"]
        # Only where the dex says which species it is; a Trainer has no
        # English name to borrow, and inventing one would make it findable
        # under a word that is not on it.
        a.name_en = english.get(card["dex"]) if card["dex"] else None
        if a.name_en:
            n["named"] += 1
        a.variant = derive_variant(card["rarity"])
        a.layer = classify_layer(card["rarity"])
        if card["dex"]:
            n["dex"] += 1

    db.commit()
    return n


def download(dest: Path) -> Path:
    print(f"Downloading {REPO_URL} …")
    req = urllib.request.Request(REPO_URL, headers={"User-Agent": "your-loot-seed"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = resp.read()
    print(f"  {len(data) // (1024 * 1024)} MB — extracting…")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    return next(dest.glob("cards-database-*"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--download", action="store_true", help="fetch the repo and seed")
    p.add_argument("--repo", type=Path, help="a checkout of tcgdex/cards-database")
    p.add_argument("--dry-run", action="store_true", help="say what it would do")
    p.add_argument("--skip-art-check", action="store_true",
                   help="assume no artwork rather than asking the asset host")
    p.add_argument("--check-empty", action="store_true",
                   help="exit 0 if no Japanese cards are seeded yet (for the entrypoint)")
    args = p.parse_args()

    # Asked before anything is downloaded, so a container that already has
    # the Japanese catalogue starts as fast as one that was never asked for
    # it. Thirteen thousand rows do not need re-fetching every boot.
    if args.check_empty:
        with SessionLocal() as db:
            seeded = db.scalar(
                select(CollectionItem.id)
                .where(CollectionItem.source == SOURCE).limit(1)
            )
        raise SystemExit(1 if seeded else 0)

    tmp = None
    if args.repo:
        root = args.repo
    elif args.download or args.dry_run:
        tmp = tempfile.TemporaryDirectory()
        root = download(Path(tmp.name))
    else:
        p.error("pass --download, or --repo with a checkout")

    cards, sets = collect(root)
    print(f"  {len(cards)} Japanese cards across {len(sets)} sets")

    illustrated: set[str] = set()
    if not args.skip_art_check:
        probes = []
        for set_id, meta in sets.items():
            first = next(c for c in cards if c["set_id"] == set_id)
            probes.append((set_id, meta["serie"], first["number"]))
        print(f"  asking the asset host about {len(probes)} sets…")
        illustrated = sets_with_art(probes)
        have = sum(1 for c in cards if c["set_id"] in illustrated)
        print(f"  {len(illustrated)}/{len(sets)} sets illustrated — {have} cards with art")

    if args.dry_run:
        pk = sum(1 for c in cards if c["category"] == "Pokemon")
        print(f"  would import {len(cards)} cards "
              f"({pk} Pokémon, {sum(1 for c in cards if c['dex'])} with a dex number)")
        print("  dry run — nothing written")
        return

    with SessionLocal() as db:
        n = seed(db, cards, sets, illustrated)
    print(f"  created {n['created']}, updated {n['updated']}, "
          f"{n['dex']} filed by dex number, {n['with_art']} with art")

    if tmp:
        tmp.cleanup()


if __name__ == "__main__":
    main()
