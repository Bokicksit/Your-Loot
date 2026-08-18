"""Does a backup actually bring everything back?

Backup and restore is the feature nobody exercises until the worst possible
moment, and by then a bug in it is indistinguishable from having no backup at
all. It's also the answer the app gives to "take a copy before you upgrade",
which makes it load-bearing for every migration in the project.

So this does the real thing: makes a backup and loads it into a second
install, then checks it arrived.

A whole-server restore is only allowed into an install with nothing in it —
a rebuilt machine, new hardware, a fresh database — so there is an API in the
stack that exists for no other reason, pointed at a database nothing else
touches. Which also means these tests are no longer destructive: they take a
copy of one install and fill an empty one, and the install they run against
is left exactly as it was.

Order matters once, and only here: the corrupt-file test needs the fresh
install to still be empty, so it goes first. The test after it fills that
install and then proves the door has shut behind it.
"""

import io
import os
import uuid

import httpx
import pytest

from conftest import OWNER_PASSWORD

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
FRESH = os.environ.get("LOOT_FRESH_URL")

needs_fresh = pytest.mark.skipif(
    not FRESH, reason="no empty install to restore into"
)


@pytest.fixture
def fresh():
    """A client for the install that has nothing in it.

    It is only empty once. The test below fills it — that is what it is for —
    and after that the stack has to be recreated (`down -v`) before these can
    run again. Skipped rather than failed in that state: a stale volume is a
    fact about the machine, not a bug in the code.
    """
    c = httpx.Client(base_url=FRESH, timeout=300)
    me = c.get("/api/auth/me").json()
    if me.get("locked") or not me.get("user"):
        c.close()
        pytest.skip("the empty install has already been filled — recreate the stack")
    yield c
    c.close()


def _titles(c: httpx.Client, tag: str) -> set[str]:
    """The titles this test made, and only those.

    Asked for by name rather than read off the first page of everything. A
    capped list sorted by title quietly stops containing "Kept ..." once the
    other modules have left a couple of hundred games called "Alice ..." and
    "Shared ..." ahead of it — which passes on a fresh stack and fails on a
    busy one, the worst way for a backup test to go wrong. The same fix as
    test_tenancy.py and test_tags.py.
    """
    found = c.get("/api/games", params={"search": tag, "limit": 200}).json()["items"]
    return {i["title"] for i in found}


@needs_fresh
def test_a_corrupt_file_is_refused_rather_than_applied(fresh):
    """The failure that would otherwise be silent and total: half a restore
    from a truncated file leaves nothing to go back to.

    First in the file on purpose. It needs an install that would otherwise
    accept a restore, and the test below fills the only one there is.
    """
    r = fresh.post(
        "/api/backup/restore",
        files={"file": ("not-a-backup.zip", io.BytesIO(b"this is not a zip"),
                        "application/zip")},
    )
    assert r.status_code >= 400, "a corrupt file was accepted"
    assert fresh.get("/api/games", params={"limit": 1}).json()["total"] == 0, (
        "a refused restore left something behind"
    )


@needs_fresh
def test_a_backup_fills_an_empty_install_and_then_the_door_shuts(owner, fresh):
    """The path somebody rebuilds a machine with, and the one that makes this
    feature worth having at all.

    The second half is the point of the change: once there is a collection in
    it, the same file is refused. Nothing that is already on a server can be
    replaced by a restore, including by the person who runs it.
    """
    tag = uuid.uuid4().hex[:8]
    kept = f"Kept {tag}"
    item = owner.post("/api/games", json={"title": kept}).json()
    owner.post(
        f"/api/items/{item['id']}/owned", json={"condition": "NM"}
    ).raise_for_status()

    blob = owner.get("/api/backup").content
    assert len(blob) > 0, "the backup is empty"

    loaded = fresh.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", io.BytesIO(blob), "application/zip")},
    )
    loaded.raise_for_status()

    # The accounts came with it, and so did the lock on the door — which is
    # the whole point of a whole-server restore and also means this client is
    # now a stranger to the install it just filled.
    assert fresh.get("/api/auth/me").json()["locked"] is True
    fresh.post("/api/auth/login", json={"password": OWNER_PASSWORD}).raise_for_status()

    assert kept in _titles(fresh, tag), "the restore did not bring the item"
    row = next(
        i for i in fresh.get(
            "/api/games", params={"search": tag, "limit": 200}
        ).json()["items"] if i["title"] == kept
    )
    assert len(row["owned"]) == 1, "the copy did not come with it"

    again = fresh.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", io.BytesIO(blob), "application/zip")},
    )
    assert again.status_code == 409, "a second restore could have replaced it"


def test_a_live_install_will_not_be_replaced(owner):
    """The door that used to be open. It deleted every row for every account
    and reloaded from a file, and one mis-click was the whole server."""
    tag = uuid.uuid4().hex[:8]
    kept = f"Still here {tag}"
    item = owner.post("/api/games", json={"title": kept}).json()
    # owned, not merely catalogued: a shelf is what you have a copy of, so an
    # entry without one would be missing from the check for the wrong reason
    owner.post(
        f"/api/items/{item['id']}/owned", json={"condition": "NM"}
    ).raise_for_status()
    blob = owner.get("/api/backup").content

    r = owner.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", io.BytesIO(blob), "application/zip")},
    )
    assert r.status_code == 409, "a live install accepted a whole-server restore"
    assert "Settings" in r.json()["detail"], "refused without saying what to do instead"
    assert kept in _titles(owner, tag), "the refusal cost something anyway"
