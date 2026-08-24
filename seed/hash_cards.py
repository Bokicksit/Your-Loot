"""Fingerprint the card catalogue, so a photograph can be matched against it.

    docker compose exec api python /seed/hash_cards.py
    docker compose exec api python /seed/hash_cards.py --limit 500   # a taste

Every card's artwork is fetched once, reduced to the sixty-four bits that say
what it looks like (app/arthash.py), and written back to `card_attrs`. The
pictures are not kept — eight bytes a card is the whole point, and the art
already lives wherever the app loads it from.

Run automatically on each start where HASH_CARD_ART=true (entrypoint.sh), or
by hand. Either way the first run is twenty thousand requests to somebody
else's CDN — a thing to start deliberately — and every later run does only
the cards added or re-illustrated since, because a changed picture clears
its fingerprint.

The loop itself lives in app/arthash_run.py, shared with the admin panel's
"create fingerprints" button so the two can never disagree about what
pending means. Idempotent and resumable; `--again` re-reads everything, for
the day the hash itself changes.
"""

import argparse
import sys

sys.path.insert(0, "/app")

from app.arthash_run import run_pending  # noqa: E402
from app.db import SessionLocal  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--again", action="store_true",
                    help="re-fingerprint cards that already have one")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after this many cards")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        tally = run_pending(db, again=args.again, limit=args.limit,
                            log=lambda m: print(m, flush=True))
        if not tally["total"]:
            print("Nothing to do — every illustrated card already has a fingerprint.")
        else:
            print(f"Done. {tally['done']} fingerprinted, {tally['missing']} "
                  f"unreachable, {tally['unreadable']} unreadable.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
