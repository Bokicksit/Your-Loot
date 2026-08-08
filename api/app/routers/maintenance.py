"""TEMPORARY — a button for the one-off backfill. Delete this whole file when
the collection has been filled in, along with:

  - `maintenance` in app/main.py (the import and the include_router)
  - `MaintenanceCard` in web/src/pages/SettingsPage.jsx
  - `backfillStart` / `backfillStatus` in web/src/api.js

`python -m app.backfill` stays either way; this is only the convenience of not
having to open a shell on the NAS. It is deliberately one self-contained file
so removing it is one deletion and three lines, not an excavation.

It runs in the background and reports progress rather than blocking, because
a collection of any size spends a second per item being polite to Open Library
and Discogs, and a request that takes four minutes is a request that hits a
proxy timeout instead of finishing.
"""

import threading

from fastapi import APIRouter, BackgroundTasks, Depends

from app import backfill
from app.auth import require_admin

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

_lock = threading.Lock()
_state: dict = {"running": False, "done": False, "log": [], "summary": None, "error": None}

MAX_LINES = 500  # a very long run shouldn't grow this without limit


def _say(line: str) -> None:
    log = _state["log"]
    log.append(line)
    if len(log) > MAX_LINES:
        del log[: len(log) - MAX_LINES]


def _work() -> None:
    try:
        _state["summary"] = backfill.run(say=_say)
    except Exception as e:  # a failed backfill must not take the app with it
        _state["error"] = f"{type(e).__name__}: {e}"
        _say(f"stopped: {_state['error']}")
    finally:
        _state["running"] = False
        _state["done"] = True


@router.get("/backfill")
def status(_=Depends(require_admin)):
    return _state


@router.post("/backfill")
def start(background: BackgroundTasks, _=Depends(require_admin)):
    with _lock:
        if _state["running"]:
            return _state
        _state.update(running=True, done=False, log=[], summary=None, error=None)
    background.add_task(_work)
    return _state
