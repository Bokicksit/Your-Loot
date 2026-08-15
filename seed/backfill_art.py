"""Move card pictures onto TCGdex's asset host, where that art exists.

Every card is seeded pointing at images.pokemontcg.io, which belongs to the
project that publishes the card dump and which never agreed to serve anybody
else's users. TCGdex publishes its assets under MIT for this purpose.

Usage (inside the api container):
    python /seed/backfill_art.py              # the whole catalogue
    python /seed/backfill_art.py --set sv8pt5 # one set, to try it out
    python /seed/backfill_art.py --dry-run    # say what would move

Safe to run twice: a card already moved is skipped, and a photograph the
collector uploaded is never touched. Cards TCGdex has no art for keep the URL
they have — about one in twenty, concentrated in Shiny Vault, the Trainer
Galleries and the Galarian Gallery.

To undo it, point the images back at the dump by re-seeding with an empty
image column:
    UPDATE collection_item SET image_url = NULL
     WHERE image_url LIKE 'https://assets.tcgdex.net/%';
    python /seed/seed_cards.py --download
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.card_art import backfill  # noqa: E402
from app.db import SessionLocal  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--set", dest="only", help="one set code, e.g. sv8pt5")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would move without writing")
    args = p.parse_args()

    db = SessionLocal()
    try:
        result = backfill(db, only=args.only, write=not args.dry_run, log=print)
    finally:
        db.close()

    print(
        f"\n{result['moved']} cards moved to TCGdex, "
        f"{result['kept']} left where they were (no art), "
        f"across {result['sets']} sets"
        + (f", {result['sets_unmatched']} unmatched" if result["sets_unmatched"] else "")
        + (" — dry run, nothing written" if args.dry_run else "")
    )


if __name__ == "__main__":
    main()
