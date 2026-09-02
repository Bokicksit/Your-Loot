"""Send this collection to another Your Loot, so its public page stays current.

The case it exists for: a collection kept on a home server, and a public page
on the hosted service. Putting the home server on the internet to serve that
page is exactly what nobody should do — so instead the home server pushes its
collection *out*, into an account on the service, and the service's public
page reads from that. Nothing reaches in. The account it lands in is a
mirror, replaced wholesale on every push; whatever is edited there is
overwritten by the next one, and the settings screen says so.

Almost none of this is new. The file that travels is the "Your collection"
backup (mine.to_zip), which already identifies every catalogue item by where
it came from so that it can be matched on another server. The receiving end
is the "restore my collection" endpoint that already exists, reached with a
bearer token minted on the target account — a token with the `sync` scope,
which can call that one endpoint and nothing else, because a token stored on
somebody's NAS is not a secret anybody should have to defend.

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import mine
from app.auth import current_user
from app.config import settings
from app.db import SessionLocal, get_db
from app.models import Setting, User
from app.ratelimit import outbound

router = APIRouter(prefix="/api/sync", tags=["sync"])

# A push is one zip, sometimes a large one, to a server that then has to load
# it in a transaction. Generous, and a slow link should not be a failure.
TIMEOUT = 600
# The nightly run: how often the loop looks, and how old a mirror has to be
# before it is refreshed. Twenty hours rather than twenty-four so that a
# machine which happens to check at 02:00 one night and 02:30 the next does
# not skip a day for the sake of half an hour.
EVERY = 60 * 60
STALE = 20 * 60 * 60


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
        "last_at": _get(db, uid, "sync_last_at"),
        "last_result": json.loads(result) if result else None,
        "last_error": _get(db, uid, "sync_last_error"),
    }


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


# --- the push ------------------------------------------------------------------

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

    blob = mine.to_zip(db, user)
    try:
        r = httpx.post(
            f"{url}/api/backup/mine",
            headers={"Authorization": f"bearer {token}", "User-Agent": "your-loot-sync/1.0"},
            files={"file": ("collection.zip", blob, "application/zip")},
            data={"confirm": mine.CONFIRM},
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as e:
        _record(db, user.id, error=f"could not reach {url}: {e.__class__.__name__}")
        raise SyncError(f"could not reach {url}") from e

    if r.status_code >= 400:
        try:
            detail = r.json().get("detail") or r.text
        except ValueError:
            detail = r.text
        msg = {
            401: "the token was refused — it may have been revoked; make a new one there",
            403: "the token was refused — it may have been revoked; make a new one there",
            404: "that address is not a Your Loot, or is too old to receive a collection",
        }.get(r.status_code, str(detail)[:300])
        _record(db, user.id, error=msg)
        raise SyncError(msg)

    result = r.json()
    _record(db, user.id, result=result)
    return result


def _record(db: Session, uid: int, *, result: dict | None = None, error: str | None = None):
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    if result is not None:
        _set(db, uid, "sync_last_at", now)
        _set(db, uid, "sync_last_result", json.dumps(result))
        _set(db, uid, "sync_last_error", None)
    else:
        _set(db, uid, "sync_last_error", error)
    db.commit()


# --- the nightly loop ----------------------------------------------------------

_started = threading.Event()


def _due(db: Session) -> list[int]:
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


def run_due() -> int:
    """One pass: push for everybody who is due. Returns how many were tried."""
    with SessionLocal() as db:
        ids = _due(db)
    for uid in ids:
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
    """A thread that looks once an hour for accounts due a push.

    Started with the app rather than as a separate process because this is a
    home server and one container is the whole point. Cheap when nobody has
    asked for it: one query an hour and back to sleep.
    """
    if _started.is_set():
        return
    _started.set()

    def loop():
        time.sleep(90)  # let migrations and the seed settle first
        while True:
            try:
                run_due()
            except Exception:  # noqa: BLE001 — the loop must outlive any one bad hour
                pass
            time.sleep(EVERY)

    threading.Thread(target=loop, name="sync-nightly", daemon=True).start()


# --- the endpoints -------------------------------------------------------------

class SyncIn(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    # None keeps the token already stored, so the address or the schedule can
    # be changed without pasting the secret again
    token: str | None = Field(default=None, max_length=200)
    nightly: bool = False


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
    db.commit()
    return status(db, user.id)


@router.delete("", status_code=204)
def forget_sync(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Stop, and forget the token. The mirror keeps what it was last sent."""
    for key in mine.SYNC_KEYS:
        _set(db, user.id, key, None)
    db.commit()


@router.post("/now", dependencies=[Depends(outbound)])
def sync_now(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        result = push(db, user)
    except SyncError as e:
        raise HTTPException(502, str(e))
    return {"result": result, **status(db, user.id)}
