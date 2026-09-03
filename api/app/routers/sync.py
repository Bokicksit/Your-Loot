"""Send this collection to another Your Loot, so its public page stays current.

The case it exists for: a collection kept on a home server, and a public page
on the hosted service. Putting the home server on the internet to serve that
page is exactly what nobody should do — so instead the home server pushes its
collection *out*, into an account on the service, and the service's public
page reads from that. Nothing reaches in. The account it lands in is a
mirror, replaced wholesale on every push; whatever is edited there is
overwritten by the next one, and both ends say so — the sender in its
settings, the receiver with a bar across the top of every page.

Almost none of this is new. The file that travels is the "Your collection"
backup (mine.to_zip), which already identifies every catalogue item by where
it came from so that it can be matched on another server. The receiving end
is the "restore my collection" endpoint that already exists, reached with a
bearer token minted on the target account — a token with the `sync` scope,
which can call that endpoint and nothing else, because a token stored on
somebody's NAS is not a secret anybody should have to defend.

Three refinements on top of "post the zip":

*Only the photos the other side lacks travel.* Before the push, the receiver
is asked which of the files this collection points at it already has, and
the zip carries the rest. Names are content hashes, so a file it has is the
same picture; a collection with a thousand photographs syncs a thousand of
them once and then none.

*It can send itself after you change something.* A change marks the account
as pending; a few minutes after the last change, it goes. So the public page
is current within minutes rather than by tomorrow, without one push per
keystroke.

*The receiver knows it is a mirror.* A restore that arrived on a sync token
stamps the account, and the app there draws a bar saying so, because the
alternative is somebody adding a card on the hosted side and watching it
vanish overnight with no explanation.

What is stored here is where to send it and the token to send it with, per
account, in the settings table under keys the export deliberately leaves out
(mine.SYNC_KEYS): a mirror must not inherit the instruction to mirror itself
onward. The token is never returned to a browser once saved; its first few
characters are, so a person can tell which one it is.
"""

import json
import threading
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app import mine
from app.auth import current_user
from app.config import settings
from app.db import SessionLocal, get_db
from app.models import (
    ApiToken, Binder, BinderSlot, CollectionItem, ItemTag, Owned, Setting, Tag, User, Wanted,
)
from app.ratelimit import outbound

router = APIRouter(prefix="/api/sync", tags=["sync"])

# A push is one zip, sometimes a large one, to a server that then has to load
# it in a transaction. Generous, and a slow link should not be a failure.
TIMEOUT = 600
# The loop wakes every minute: often enough that "a few minutes after the
# last change" means what it says, cheap enough — one dictionary look — that
# nobody notices it exists.
TICK = 60
# The nightly run: how old a mirror has to be before it is refreshed. Twenty
# hours rather than twenty-four so that a machine which happens to check at
# 02:00 one night and 02:30 the next does not skip a day for half an hour.
STALE = 20 * 60 * 60
# After a change, how long to wait for the next one before sending. Long
# enough that filing twenty cards is one push, short enough that the public
# page is right before you have finished telling somebody about it.
DEBOUNCE = 5 * 60


class SyncError(Exception):
    pass


# --- the settings rows ---------------------------------------------------------

def _get(db: Session, uid: int, key: str) -> str | None:
    row = db.get(Setting, (uid, key))
    return row.value if row else None


def _set(db: Session, uid: int, key: str, value: str | None) -> None:
    row = db.get(Setting, (uid, key))
    if value is None:
        if row is not None:
            db.delete(row)
        return
    if row is None:
        row = Setting(user_id=uid, key=key)
        db.add(row)
    row.value = value


def status(db: Session, uid: int) -> dict:
    token = _get(db, uid, "sync_token") or ""
    result = _get(db, uid, "sync_last_result")
    return {
        "configured": bool(_get(db, uid, "sync_url") and token),
        "url": _get(db, uid, "sync_url"),
        # enough to recognise it in the target's token list, never the value
        "token_prefix": token[:8] if token else None,
        "nightly": _get(db, uid, "sync_nightly") == "1",
        "on_change": _get(db, uid, "sync_on_change") == "1",
        # a change has been made since the last send and is waiting its turn
        "pending": uid in _pending,
        "last_at": _get(db, uid, "sync_last_at"),
        "last_result": json.loads(result) if result else None,
        "last_error": _get(db, uid, "sync_last_error"),
    }


# --- the receiving side: knowing you are a mirror -------------------------------

def mark_mirror(db: Session, uid: int, source: str | None) -> None:
    """Called by the restore endpoint when what arrived came on a sync token."""
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    _set(db, uid, "mirrored_at", now)
    _set(db, uid, "mirror_source", (source or "").strip()[:200] or "another Your Loot")


def mirror_status(db: Session, uid: int) -> dict | None:
    at = _get(db, uid, "mirrored_at")
    if not at:
        return None
    return {"at": at, "source": _get(db, uid, "mirror_source") or "another Your Loot"}


def stop_mirroring(db: Session, uid: int) -> int:
    """Forget that this account is a mirror, and revoke every token that
    could make it one again. Returns how many tokens were revoked."""
    for key in mine.MIRROR_KEYS:
        _set(db, uid, key, None)
    now = datetime.now(UTC).replace(tzinfo=None)
    rows = db.scalars(
        select(ApiToken).where(
            ApiToken.user_id == uid, ApiToken.scope == "sync", ApiToken.revoked_at.is_(None)
        )
    ).all()
    for t in rows:
        t.revoked_at = now
    return len(rows)


# --- where it may go -----------------------------------------------------------

def validate_url(raw: str) -> str:
    """The base address of the other install, checked the way a pasted image
    URL is: a scheme this can speak, a host, and — unless the operator has
    said the other machine is on their own network — nowhere private.

    Returned without a trailing slash and without a path: the endpoint is
    known and appended here, so somebody pasting the whole address of their
    account page still ends up at the right place.
    """
    u = urlparse((raw or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise SyncError("give the address of the other Your Loot, like https://yourloot.app")
    if not settings.sync_allow_private:
        from app.routers.images import _safe_address  # the SSRF guard, unchanged

        try:
            _safe_address(u.hostname)
        except HTTPException as e:
            raise SyncError(
                f"{e.detail} — set SYNC_ALLOW_PRIVATE=true if the other install "
                f"really is on your own network"
            ) from None
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{u.hostname}{port}"


def _source_label() -> str:
    """How this install introduces itself to the mirror. The public address
    where one is configured; otherwise the honest generic."""
    url = (settings.public_url or "").strip().rstrip("/")
    if url and "localhost" not in url and "127.0.0.1" not in url:
        return url
    return "your home server"


# --- the push ------------------------------------------------------------------

def _missing_images(url: str, headers: dict, names: set[str]) -> set[str] | None:
    """Ask the other side which of these files it does not have.

    None means "could not ask" — an older install without the endpoint, or a
    hiccup — and the caller sends everything, which is what always worked.
    """
    if not names:
        return set()
    try:
        r = httpx.post(
            f"{url}/api/backup/mine/have",
            headers=headers, json={"names": sorted(names)}, timeout=60,
        )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        return set(r.json().get("missing") or [])
    except ValueError:
        return None


def push(db: Session, user: User) -> dict:
    """Send this account's collection to the configured target, now.

    Records how it went either way — the time and the target's summary on
    success, the reason on failure — so the settings screen can say "last
    synced 2 hours ago · 1,340 copies" or "failed: plan allows 300 cards"
    without anybody having to watch it happen.
    """
    url, token = _get(db, user.id, "sync_url"), _get(db, user.id, "sync_token")
    if not url or not token:
        raise SyncError("nowhere to send it yet — set the address and token first")
    headers = {"Authorization": f"bearer {token}", "User-Agent": "your-loot-sync/1.0"}

    payload = mine.gather(db, user)
    only = _missing_images(url, headers, mine._images_for(payload))
    blob = mine.to_zip(db, user, payload=payload, only_images=only)
    _pending.pop(user.id, None)   # whatever was waiting is in this one
    try:
        r = httpx.post(
            f"{url}/api/backup/mine",
            headers=headers,
            files={"file": ("collection.zip", blob, "application/zip")},
            data={"confirm": mine.CONFIRM, "source": _source_label()},
            timeout=TIMEOUT,
        )
    except httpx.TimeoutException as e:
        msg = (f"{url} took too long to answer. A first send carries every photo; "
               f"try again and it will carry only what is left.")
        _record(db, user.id, error=msg)
        raise SyncError(msg) from e
    except httpx.HTTPError as e:
        msg = f"could not reach {url} ({e.__class__.__name__})"
        _record(db, user.id, error=msg)
        raise SyncError(msg) from e

    if r.status_code >= 400:
        _record(db, user.id, error=explain(r, url, len(blob)))
        raise SyncError(explain(r, url, len(blob)))

    result = r.json()
    _record(db, user.id, result=result)
    return result


def explain(r: httpx.Response, url: str, sent: int) -> str:
    """Why the other end said no, in words that name the next step.

    Worth the care: this string is the whole diagnosis. Everything the sender
    can go wrong at surfaces here as one 502, and "Internal Server Error"
    passed through from the far side tells nobody anything — the status is
    what says whether the fault is the token, the size, the plan, or that
    server having a bad moment.
    """
    try:
        detail = str(r.json().get("detail") or "").strip()
    except ValueError:
        detail = ""
    mb = sent / (1024 * 1024)

    if r.status_code in (401, 403):
        return ("the token was refused — it may have been revoked, or it may "
                "belong to a different account. Make a new one there and paste it in.")
    if r.status_code == 404:
        return f"{url} is not a Your Loot, or is too old to receive a collection"
    if r.status_code == 413:
        return (f"the collection is too large for that server to accept "
                f"({mb:.0f} MB). A proxy in front of it is refusing the upload — "
                f"Cloudflare's free plan stops at 100 MB.")
    if r.status_code == 429:
        return "that server is rate-limiting this account — wait a minute and try again"
    if r.status_code == 400 and detail:
        # the receiver's own words: the plan check, a bad file, a missing
        # confirmation. These are already written for a person.
        return detail[:300]
    if r.status_code in (502, 503, 504, 522, 524):
        return (f"{url} did not answer in time (HTTP {r.status_code}). The send "
                f"was {mb:.0f} MB; a large first send can outlast a proxy's "
                f"timeout, and trying again sends only what is left.")
    if r.status_code >= 500:
        return (f"that server hit an error loading the collection "
                f"(HTTP {r.status_code}{f': {detail[:120]}' if detail else ''}). "
                f"Its logs will say why; nothing here was changed.")
    return f"HTTP {r.status_code}{f': {detail[:200]}' if detail else ''}"


def _record(db: Session, uid: int, *, result: dict | None = None, error: str | None = None):
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    if result is not None:
        _set(db, uid, "sync_last_at", now)
        _set(db, uid, "sync_last_result", json.dumps(result))
        _set(db, uid, "sync_last_error", None)
    else:
        _set(db, uid, "sync_last_error", error)
    db.commit()


# --- send it after a change ----------------------------------------------------

# account id -> when it last changed, on the monotonic clock. In memory: a
# restart loses at most one pending push, and the nightly run catches it.
_pending: dict[int, float] = {}
_pending_lock = threading.Lock()


def notify_change(uid: int | None) -> None:
    if uid is None:
        return
    with _pending_lock:
        _pending[uid] = time.monotonic()


def _changes_due(now: float | None = None) -> list[int]:
    """Accounts whose last change is older than the debounce."""
    now = time.monotonic() if now is None else now
    with _pending_lock:
        return [uid for uid, at in _pending.items() if now - at >= DEBOUNCE]


def _owner_of(obj):
    """Whose collection a changed row belongs to, or None if it is nobody's."""
    if isinstance(obj, (Owned, Wanted, Binder, Tag)):
        return obj.user_id
    if isinstance(obj, BinderSlot):
        b = obj.binder
        return b.user_id if b is not None else None
    if isinstance(obj, ItemTag):
        t = obj.tag
        return t.user_id if t is not None else None
    if isinstance(obj, CollectionItem):
        return obj.private_to   # your own photo on your own hand-typed item
    return None


@event.listens_for(Session, "after_flush")
def _watch_changes(session, _ctx):
    """Every write to somebody's collection marks them pending.

    Listening on the session rather than editing every handler means a new
    route that files a card cannot forget to say so — the row itself says so.
    Marked on flush rather than commit, which can over-count on a rollback;
    an extra push of an unchanged collection costs a request, not correctness.
    """
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        uid = _owner_of(obj)
        if uid is not None:
            notify_change(uid)


# --- the loop ------------------------------------------------------------------

_started = threading.Event()


def _due_nightly(db: Session) -> list[int]:
    """Accounts that asked for a nightly push and have not had one lately."""
    rows = db.scalars(
        select(Setting).where(Setting.key == "sync_nightly", Setting.value == "1")
    ).all()
    due = []
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in rows:
        last = _get(db, row.user_id, "sync_last_at")
        try:
            age = (now - datetime.fromisoformat(last)).total_seconds() if last else None
        except ValueError:
            age = None
        if age is None or age > STALE:
            due.append(row.user_id)
    return due


def _due_changed(db: Session) -> list[int]:
    """Pending accounts that asked to be sent after changes. The rest are
    forgotten: they changed, but nobody asked for that to mean anything."""
    out = []
    for uid in _changes_due():
        if _get(db, uid, "sync_on_change") == "1" and _get(db, uid, "sync_url"):
            out.append(uid)
        else:
            _pending.pop(uid, None)
    return out


def run_due(nightly: bool = True) -> int:
    """One pass: push for everybody who is due. Returns how many were tried."""
    with SessionLocal() as db:
        ids = set(_due_changed(db))
        if nightly:
            ids |= set(_due_nightly(db))
    for uid in sorted(ids):
        with SessionLocal() as db:
            user = db.get(User, uid)
            if user is None:
                continue
            try:
                push(db, user)
            except SyncError:
                pass  # recorded against the account; the screen will say
            except Exception as e:  # noqa: BLE001 — one account must not stop the rest
                _record(db, uid, error=f"unexpected: {e.__class__.__name__}")
    return len(ids)


def start_scheduler() -> None:
    """A thread that wakes every minute for changes and once an hour for the
    nightly list.

    Started with the app rather than as a separate process because this is a
    home server and one container is the whole point. Cheap when nobody has
    asked for it: a dictionary look a minute, a query an hour.
    """
    if _started.is_set():
        return
    _started.set()

    def loop():
        time.sleep(90)  # let migrations and the seed settle first
        tick = 0
        while True:
            try:
                run_due(nightly=(tick % 60 == 0))
            except Exception:  # noqa: BLE001 — the loop must outlive any one bad minute
                pass
            tick += 1
            time.sleep(TICK)

    threading.Thread(target=loop, name="sync", daemon=True).start()


# --- the endpoints -------------------------------------------------------------

class SyncIn(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    # None keeps the token already stored, so the address or the schedule can
    # be changed without pasting the secret again
    token: str | None = Field(default=None, max_length=200)
    nightly: bool = False
    on_change: bool = False


@router.get("")
def get_sync(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return status(db, user.id)


@router.put("")
def put_sync(body: SyncIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        url = validate_url(body.url)
    except SyncError as e:
        raise HTTPException(400, str(e))
    token = (body.token or "").strip() or _get(db, user.id, "sync_token")
    if not token:
        raise HTTPException(400, "paste the sync token from the other account")
    _set(db, user.id, "sync_url", url)
    _set(db, user.id, "sync_token", token)
    _set(db, user.id, "sync_nightly", "1" if body.nightly else "0")
    _set(db, user.id, "sync_on_change", "1" if body.on_change else "0")
    db.commit()
    # saving the settings is itself a flush; that is not a change to send
    _pending.pop(user.id, None)
    return status(db, user.id)


@router.delete("", status_code=204)
def forget_sync(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Stop, and forget the token. The mirror keeps what it was last sent."""
    for key in mine.SYNC_KEYS:
        _set(db, user.id, key, None)
    db.commit()
    _pending.pop(user.id, None)


@router.post("/now", dependencies=[Depends(outbound)])
def sync_now(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        result = push(db, user)
    except SyncError as e:
        raise HTTPException(502, str(e))
    return {"result": result, **status(db, user.id)}


@router.delete("/mirror")
def stop_mirror(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """This account stops being a mirror: the bar goes, and every sync token
    on it is revoked so the next send from the old source is refused."""
    revoked = stop_mirroring(db, user.id)
    db.commit()
    return {"revoked_tokens": revoked}
