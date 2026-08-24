"""The fingerprinting pass itself, shared by everything that starts one.

Two callers want the same loop: seed/hash_cards.py, run from a shell on a
schedule of somebody's choosing, and the admin panel's button, run after
curating a set's artwork. One implementation, so "what counts as pending"
and "how a picture becomes eight bytes" cannot quietly disagree between
them — the exact drift that left amiibo exports empty for three versions.

A card's art can live in two places now: on a catalogue CDN, or in our own
IMAGE_DIR once an administrator has uploaded or pulled a replacement. The
loop reads whichever the URL says. Local files are the cheap case and are
deliberately not paced; the pause exists to be polite to somebody else's
server, and there is nobody to be polite to on our own disk.
"""

import time
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import arthash
from app.config import settings
from app.models import CardAttrs, CollectionItem, Module

PAUSE = 0.04     # between CDN fetches — polite, and this only ever runs once per card
TIMEOUT = 20
BATCH = 200      # commit cadence, so an interrupted run keeps what it did


def _pending_query(again: bool = False):
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
    return q


def pending_count(db: Session) -> int:
    """How many illustrated cards still have no fingerprint."""
    return db.scalar(
        select(func.count())
        .select_from(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            CollectionItem.module == Module.cards.value,
            CollectionItem.image_url.is_not(None),
            CardAttrs.art_hash.is_(None),
        )
    ) or 0


def _read(client: httpx.Client, url: str) -> bytes | None:
    """The picture behind a card's image_url, wherever it lives.

    A /images/ URL is our own disk — an upload, or art localised from a
    link — and is read as a file. Anything else is fetched. None for
    anything unreachable; the card stays pending and the next run retries.
    """
    if url.startswith("/images/"):
        name = url.split("/images/", 1)[1].split("?", 1)[0]
        if "/" in name or "\\" in name or name.startswith("."):
            return None
        path = Path(settings.image_dir) / name
        try:
            return path.read_bytes()
        except OSError:
            return None
    try:
        r = client.get(url)
        return r.content if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def run_pending(
    db: Session,
    *,
    again: bool = False,
    limit: int | None = None,
    log=lambda msg: None,
) -> dict:
    """Fingerprint everything pending. Returns the tally.

    Commits as it goes, so stopping it loses at most a batch — which is what
    lets both callers treat it as interruptible.
    """
    q = _pending_query(again)
    if limit:
        q = q.limit(limit)
    todo = db.execute(q).all()
    done = missing = unreadable = 0
    if not todo:
        return {"done": 0, "missing": 0, "unreadable": 0, "total": 0}

    log(f"fingerprinting {len(todo)} cards")
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": "your-loot/1.0"}) as client:
        for n, (item, attrs) in enumerate(todo, 1):
            local = item.image_url.startswith("/images/")
            data = _read(client, item.image_url)
            if data is None:
                missing += 1
                continue
            value = arthash.fingerprint(data)
            if value is None:
                unreadable += 1
                continue
            attrs.art_hash = arthash.to_signed(value)
            done += 1
            if n % BATCH == 0:
                db.commit()
                log(f"  {n}/{len(todo)} · {done} fingerprinted")
            if not local:
                time.sleep(PAUSE)
    db.commit()
    return {"done": done, "missing": missing, "unreadable": unreadable, "total": len(todo)}
