"""Fingerprint the card catalogue, so a photograph can be matched against it.

    docker compose exec api python /seed/hash_cards.py
    docker compose exec api python /seed/hash_cards.py --limit 500   # a taste

Every card's artwork is fetched once, reduced to the sixty-four bits that say
what it looks like (app/arthash.py), and written back to `card_attrs`. The
pictures are not kept — eight bytes a card is the whole point, and the art
already lives on TCGdex's host where the app loads it from.

Not wired into entrypoint.sh, unlike the console catalogue. This is twenty
thousand requests to somebody else's CDN, which is a thing to start
deliberately on a night you are not using the server — not something that
happens because a container restarted. Until it has run, the scanner finds
nothing and says so; everything else about cards is unaffected.

Idempotent and resumable, both of which matter over a run this long. It only
asks about cards that have artwork and no fingerprint yet, so it can be
interrupted and started again, and a second run after the catalogue grows
does the new cards only. `--again` re-reads everything, for the day the hash
itself changes.
"""

import argparse
import sys
import time

import httpx

sys.path.insert(0, "/app")

from app import arthash  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CardAttrs, CollectionItem, Module  # noqa: E402
from sqlalchemy import select  # noqa: E402

# Polite rather than fast. The art is a gift from a project that is not
# charging us for it, and there is no hurry: this runs once.
PAUSE = 0.04
TIMEOUT = 20
# Written back in batches so an interrupted run keeps what it has done, and
# so twenty thousand commits do not become the slow part.
BATCH = 200


def rows(db, again: bool, limit: int | None):
    q = (
        select(CollectionItem, CardAttrs)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            CollectionItem.module == Module.cards.value,
            CollectionItem.image_url.is_not(None),
        )
        .order_by(CollectionItem.id)
    )
    if not again:
        q = q.where(CardAttrs.art_hash.is_(None))
    if limit:
        q = q.limit(limit)
    return db.execute(q).all()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--again", action="store_true",
                    help="re-fingerprint cards that already have one")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after this many cards")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        todo = rows(db, args.again, args.limit)
        if not todo:
            print("Nothing to do — every illustrated card already has a fingerprint.")
            return 0

        print(f"Fingerprinting {len(todo)} cards. This is a long run; it can be "
              f"stopped and started again.")
        done = missing = unreadable = 0
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                          headers={"User-Agent": "your-loot/1.0"}) as client:
            for n, (item, attrs) in enumerate(todo, 1):
                try:
                    r = client.get(item.image_url)
                    if r.status_code != 200:
                        missing += 1
                        continue
                    value = arthash.fingerprint(r.content)
                except httpx.HTTPError:
                    missing += 1
                    continue

                if value is None:
                    # A file that came back but is not a picture this can read.
                    # Left null: it will be retried by the next run, which is
                    # the right answer for a CDN having a bad afternoon.
                    unreadable += 1
                    continue

                attrs.art_hash = arthash.to_signed(value)
                done += 1

                if n % BATCH == 0:
                    db.commit()
                    print(f"  {n}/{len(todo)} · {done} fingerprinted", flush=True)
                time.sleep(PAUSE)

        db.commit()
        print(f"Done. {done} fingerprinted, {missing} unreachable, "
              f"{unreadable} unreadable.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
