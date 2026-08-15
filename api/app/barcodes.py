"""One barcode, one lookup, ever.

A barcode means the same thing this year as last, so the answer is worth
keeping. Every caller goes through here rather than reaching for the
integration directly, because a cache only half the code uses is not a cache.

What this is worth depends entirely on how many people share the install. On
one household, very little: the free tier allows a hundred calls a day and
nobody scans a hundred things. Shared, it is the difference between a cost
that grows with your users and one that grows with the number of distinct
products that exist — and the second one stops.

Misses are kept as well as hits. A barcode the provider does not know is a
real answer, and asking again this afternoon will not change it. They are
kept with a date so they can be retried after a while, since databases do
gain entries; hits are never retried, because a barcode does not change its
mind about what it is.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.upcitemdb import BarcodeError, lookup as upc_lookup
from app.models import BarcodeCache

# A miss is worth asking about again eventually — new products get added, and
# a barcode scanned the week a game came out may simply have been too early.
# A hit is not: the answer cannot change.
RETRY_MISS_AFTER = timedelta(days=30)


def lookup(db: Session, code: str) -> list[dict]:
    """What this barcode is, from the cache if anybody has asked before.

    Raises BarcodeError exactly as the integration does, so callers that
    already handle a spent quota or a bad code keep working unchanged.
    """
    row = db.get(BarcodeCache, code)
    if row is not None:
        fresh = row.found or (
            row.fetched_at is not None
            and datetime.now(UTC).replace(tzinfo=None) - row.fetched_at < RETRY_MISS_AFTER
        )
        if fresh:
            return list(row.payload or [])

    items = upc_lookup(code)  # BarcodeError propagates: nothing to cache

    if row is None:
        row = BarcodeCache(code=code)
        db.add(row)
    row.payload = items
    row.found = bool(items)
    row.fetched_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return items


def stats(db: Session) -> dict:
    """How many lookups this has saved, for anybody deciding whether a bigger
    plan is worth paying for."""
    rows = db.execute(
        select(BarcodeCache.found, func.count()).group_by(BarcodeCache.found)
    ).all()
    by = {bool(found): n for found, n in rows}
    return {
        "barcodes_known": sum(by.values()),
        "recognised": by.get(True, 0),
        "unrecognised": by.get(False, 0),
    }
