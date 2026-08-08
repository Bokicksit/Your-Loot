"""Fill in what wasn't being fetched when your existing items were added.

    docker compose exec api python -m app.backfill

Book blurbs and record tracklists are newer than most collections, so a shelf
added before them has empty fields the app now knows how to fill. This walks
what's already there and asks for the missing pieces.

It never overwrites — anything already filled in is skipped, including
anything you typed yourself. Safe to run twice, and safe to stop halfway:
every item is committed as it lands, so a run that dies at item 300 keeps the
first 299.

The identifiers are the catch. Neither module stored the source's own id back
then, so this has to re-find each item from what *is* on the row: the ISBN for
a book, the barcode for a record. Anything without one is reported rather than
guessed at, because a wrong tracklist is worse than none.
"""

import sys
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.integrations.discogs import discogs_client
from app.integrations.openlibrary import openlibrary_client
from app.models import BookAttrs, CollectionItem, RecordAttrs

# Open Library asks for politeness rather than enforcing a number; Discogs
# allows 60 requests a minute with a token. One second between calls keeps
# both comfortable and makes a big collection take minutes, not seconds.
PAUSE = 1.0


def _books(db, dry_run: bool, say) -> tuple[int, int, list[str]]:
    rows = db.scalars(
        select(BookAttrs)
        .join(CollectionItem, CollectionItem.id == BookAttrs.item_id)
        .where(BookAttrs.blurb.is_(None))
    ).all()
    filled = skipped = 0
    no_id = []
    say(f"Books without a blurb: {len(rows)}")
    for a in rows:
        title = a.item.title if a.item else f"item {a.item_id}"
        if not a.isbn:
            no_id.append(title)
            continue
        if dry_run:
            skipped += 1
            continue
        text = openlibrary_client.description_by_isbn(a.isbn)
        time.sleep(PAUSE)
        if not text:
            skipped += 1
            say(f"  —  {title}: Open Library has none")
            continue
        a.blurb = text
        db.commit()
        filled += 1
        say(f"  ok {title}: {len(text)} chars")
    return filled, skipped, no_id


def _records(db, dry_run: bool, say) -> tuple[int, int, list[str]]:
    rows = db.scalars(
        select(RecordAttrs)
        .join(CollectionItem, CollectionItem.id == RecordAttrs.item_id)
        .where(RecordAttrs.tracklist.is_(None))
    ).all()
    filled = skipped = 0
    no_id = []
    say(f"Records without a tracklist: {len(rows)}")
    if rows and not discogs_client.configured:
        say("  (no DISCOGS_TOKEN — tracklists come from Discogs, so this is a no-op)")
        return 0, len(rows), []
    for a in rows:
        title = a.item.title if a.item else f"item {a.item_id}"
        if not a.barcode:
            # A pressing is identified by its barcode. Artist and title alone
            # match the album, not the pressing, and would cheerfully attach a
            # 2011 reissue's running order to a 1977 original.
            no_id.append(title)
            continue
        if dry_run:
            skipped += 1
            continue
        hits = discogs_client.by_barcode(a.barcode, limit=5)
        time.sleep(PAUSE)
        ids = [h["discogs_id"] for h in hits if h.get("discogs_id")]
        # One barcode routinely returns the same release listed more than
        # once — different regions, the same pressing catalogued twice. That
        # is fine, and they agree on the running order. Two *different*
        # records behind one barcode is not fine, and is where this stops.
        names = {(h.get("title") or "").strip().lower() for h in hits}
        if not ids or len(names) > 1:
            skipped += 1
            why = "nothing" if not ids else f"{len(names)} different records"
            say(f"  —  {title}: that barcode matches {why}")
            continue
        text = discogs_client.tracklist(ids[0])
        time.sleep(PAUSE)
        if not text:
            skipped += 1
            say(f"  —  {title}: Discogs lists no tracks")
            continue
        a.tracklist = text
        db.commit()
        filled += 1
        say(f"  ok {title}: {len(text.splitlines())} tracks")
    return filled, skipped, no_id


def run(dry_run: bool = False, say=print) -> dict:
    """The whole pass, as data.

    Shared by the command line and the Settings button so there is one
    implementation rather than two that drift apart.
    """
    with SessionLocal() as db:
        b_filled, b_skipped, b_noid = _books(db, dry_run, say)
        r_filled, r_skipped, r_noid = _records(db, dry_run, say)
    return {
        "books": {
            "filled": b_filled,
            "nothing_found": b_skipped,
            "unidentifiable": b_noid,
        },
        "records": {
            "filled": r_filled,
            "nothing_found": r_skipped,
            "unidentifiable": r_noid,
        },
    }


def main() -> int:
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if dry_run:
        print("Dry run — counting only, nothing will be fetched or written.")

    out = run(dry_run)
    b = out["books"]
    r = out["records"]
    b_filled, b_skipped, b_noid = b["filled"], b["nothing_found"], b["unidentifiable"]
    r_filled, r_skipped, r_noid = r["filled"], r["nothing_found"], r["unidentifiable"]

    print("\n" + "-" * 52)
    print(f"Books:   {b_filled} filled, {b_skipped} had none to find")
    print(f"Records: {r_filled} filled, {r_skipped} had none to find")
    for label, missing, needs in (
        ("books", b_noid, "an ISBN"),
        ("records", r_noid, "a barcode"),
    ):
        if not missing:
            continue
        print(f"\n{len(missing)} {label} were skipped for having no {needs} to look up:")
        for t in missing[:10]:
            print(f"  · {t}")
        if len(missing) > 10:
            print(f"  … and {len(missing) - 10} more")
        print("  Re-add one from a search or a scan and it'll pick the text up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
