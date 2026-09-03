"""A copy of every linked picture somebody's collection depends on.

Most pictures in this app are links: catalogue art on TCGdex, a cover from
IGDB, a jacket from Open Library. A link is somebody else's promise, and the
promises break — a CDN reorganises, a project loses its funding, a hotlink
policy changes — and when one does, a shelf that looked complete for two
years is suddenly a wall of grey frames. The person whose shelf it is did
nothing wrong and can do nothing about it.

So this keeps a copy. For every item an entitled person owns whose picture is
a link, the file is fetched once and kept under the same directory as the
photographs people upload, and a small row remembers which item it belongs
to. The copy is a **fallback**, not a replacement: the page still asks the
link first, so corrected art upstream is still seen, and only when the link
fails does the browser turn to the copy. Nothing about how a picture is
chosen changes; only what happens when it is not there.

Who gets it is the same rule as the collector's room (plans.keeps_copies):
everybody on a self-hosted install, where nothing is sold and the disk is
your own; on a hosted service, the people paying for the disk. An item owned
by one entitled person gets its copy, and since the catalogue row is shared,
so does everybody else who happens to own it — a copy is a fact about the
picture, not the person.

Fetched slowly, in the background, a bounded batch an hour, because these are
other people's servers and a thousand-card collection is not an emergency.
"""

import hashlib
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import CollectionItem, ImageCopy, Owned, User
from app.plans import keeps_copies

# How many links to fetch in one hourly pass, and the pause between them. A
# thousand-card collection is copied over a working day, which is fine: the
# links are still up, or the copy would be too late anyway.
BATCH = 150
PAUSE = 0.25
EVERY = 60 * 60
# A link that failed is asked about again eventually — an outage is not a
# verdict — but not every hour.
RETRY_FAILED_AFTER = timedelta(days=7)

_started = threading.Event()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def entitled_user_ids(db: Session) -> set[int]:
    """Everybody whose collection earns copies. Small table, whole answer."""
    return {u.id for u in db.scalars(select(User)).all() if keeps_copies(u)}


def candidates(db: Session, limit: int = BATCH) -> list[CollectionItem]:
    """Items that want a copy and have not got one: owned by somebody
    entitled, pictured by a link, with no copy row — or a failed one old
    enough to try again."""
    who = entitled_user_ids(db)
    if not who:
        return []
    cutoff = _now() - RETRY_FAILED_AFTER
    rows = db.execute(
        select(CollectionItem, ImageCopy)
        .join(Owned, Owned.item_id == CollectionItem.id)
        .outerjoin(ImageCopy, ImageCopy.item_id == CollectionItem.id)
        .where(
            Owned.user_id.in_(who),
            CollectionItem.image_url.is_not(None),
            CollectionItem.image_url.like("http%"),
        )
        .distinct()
        .order_by(CollectionItem.id)
    ).all()
    out = []
    for item, copy in rows:
        if copy is None or (copy.name is None and copy.failed_at is not None and copy.failed_at < cutoff):
            out.append(item)
        if len(out) >= limit:
            break
    return out


def fetch(url: str) -> tuple[bytes, str]:
    """The bytes and the extension they should be kept under.

    Through the same guarded fetch a pasted image URL gets — every hop
    checked, nothing private — because a catalogue row's image_url is data
    somebody wrote, not a trusted string.
    """
    from app.routers.images import EXT_BY_TYPE, MAX_BYTES, _checked_get

    r = _checked_get(url)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    ext = EXT_BY_TYPE.get(ctype)
    if not ext:
        raise ValueError(f"not an image ({ctype or 'unknown type'})")
    if len(r.content) > MAX_BYTES:
        raise ValueError("too large")
    return r.content, ext


def copy_one(db: Session, item: CollectionItem, get=fetch) -> ImageCopy:
    """Fetch this item's linked picture and keep it. Records a failure too, so
    a dead link is not retried every hour for the rest of time."""
    row = db.get(ImageCopy, item.id) or ImageCopy(item_id=item.id)
    row.source_url = item.image_url
    try:
        data, ext = get(item.image_url)
    except Exception as e:  # noqa: BLE001 — any reason is a reason not to have it yet
        row.name = None
        row.failed_at = _now()
        row.error = str(e)[:200]
        db.add(row)
        db.commit()
        return row
    # named by content, so the same picture kept twice is one file
    name = f"copy-{hashlib.sha256(data).hexdigest()[:24]}{ext}"
    path = Path(settings.image_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    row.name = name
    row.bytes = len(data)
    row.fetched_at = _now()
    row.failed_at = None
    row.error = None
    db.add(row)
    db.commit()
    return row


def path_for(db: Session, item_id: int) -> Path | None:
    """Where the copy for this item is on disk, if there is one."""
    row = db.get(ImageCopy, item_id)
    if row is None or not row.name:
        return None
    p = Path(settings.image_dir) / row.name
    return p if p.is_file() else None


def run_pass(limit: int = BATCH, pause: float = PAUSE) -> dict:
    """One pass: copy what is due, up to the batch. Returns a small tally."""
    if not settings.keep_image_copies:
        return {"tried": 0, "kept": 0, "failed": 0, "off": True}
    with SessionLocal() as db:
        todo = candidates(db, limit)
    kept = failed = 0
    for item in todo:
        with SessionLocal() as db:
            live = db.get(CollectionItem, item.id)
            if live is None or not (live.image_url or "").startswith("http"):
                continue
            row = copy_one(db, live)
            if row.name:
                kept += 1
            else:
                failed += 1
        if pause:
            time.sleep(pause)
    return {"tried": len(todo), "kept": kept, "failed": failed, "off": False}


def start_scheduler() -> None:
    """Once an hour, in the background, for as long as the process runs."""
    if _started.is_set():
        return
    _started.set()

    def loop():
        time.sleep(180)  # after migrations, the seed, and the sync loop's own start
        while True:
            try:
                run_pass()
            except Exception:  # noqa: BLE001 — the loop must outlive any one bad hour
                pass
            time.sleep(EVERY)

    threading.Thread(target=loop, name="image-copies", daemon=True).start()
