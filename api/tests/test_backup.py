"""Does a backup actually bring everything back?

Backup and restore is the feature nobody exercises until the worst possible
moment, and by then a bug in it is indistinguishable from having no backup at
all. It's also the answer the app gives to "take a copy before you upgrade",
which makes it load-bearing for every migration in the project.

So this does the real thing: makes a backup, changes the world, restores, and
checks the world came back. It cannot be done without wiping the database it
runs against — restoring *is* replacing everything — which is why the whole
module is marked destructive and skipped unless the stack has been declared
disposable. See conftest.py.
"""

import io
import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.destructive

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


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


def test_a_backup_restores_what_it_captured(owner):
    tag = uuid.uuid4().hex[:8]
    kept = f"Kept {tag}"

    item = owner.post("/api/games", json={"title": kept}).json()
    owner.post(f"/api/items/{item['id']}/owned", json={"condition": "NM"}).raise_for_status()
    assert kept in _titles(owner, tag)

    archive = owner.get("/api/backup")
    archive.raise_for_status()
    blob = archive.content
    assert len(blob) > 0, "the backup is empty"

    # now diverge from it, in both directions
    added_after = f"Added after {tag}"
    later = owner.post("/api/games", json={"title": added_after}).json()
    owner.post(f"/api/items/{later['id']}/owned", json={"condition": "NM"})
    owner.delete(f"/api/games/{item['id']}").raise_for_status()

    now = _titles(owner, tag)
    assert kept not in now and added_after in now, "the divergence didn't take"

    restored = owner.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", io.BytesIO(blob), "application/zip")},
    )
    restored.raise_for_status()

    after = _titles(owner, tag)
    assert kept in after, "restore lost something the backup contained"
    assert added_after not in after, "restore kept something the backup never had"


def test_the_copies_come_back_too(owner):
    """An item without its copies is a catalogue entry, not a collection —
    the condition and completeness are the part that was yours."""
    tag = uuid.uuid4().hex[:8]
    item = owner.post("/api/games", json={"title": f"Copies {tag}"}).json()
    owner.post(
        f"/api/items/{item['id']}/owned",
        json={"condition": "LP", "completeness": "CIB", "notes": f"note-{tag}"},
    ).raise_for_status()

    blob = owner.get("/api/backup").content
    owner.delete(f"/api/games/{item['id']}").raise_for_status()
    owner.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", io.BytesIO(blob), "application/zip")},
    ).raise_for_status()

    found = owner.get("/api/games", params={"search": tag, "limit": 200}).json()["items"]
    row = next(i for i in found if i["title"] == f"Copies {tag}")
    assert len(row["owned"]) == 1, "the copy did not come back"
    copy = row["owned"][0]
    assert copy["condition"] == "LP"
    assert copy["completeness"] == "CIB"
    assert copy["notes"] == f"note-{tag}", "the note did not come back"


def test_a_corrupt_file_is_refused_rather_than_applied(owner):
    """The failure that would otherwise be silent and total: half a restore
    from a truncated file leaves nothing to go back to.

    Something of this test's own has to be on the shelf for "nothing changed"
    to mean anything. Comparing two unscoped pages compared the same first
    two hundred rows either way, which would have gone on passing while a
    half-applied restore quietly emptied everything behind them.
    """
    tag = uuid.uuid4().hex[:8]
    survivor = f"Survivor {tag}"
    owner.post("/api/games", json={"title": survivor}).raise_for_status()

    before = _titles(owner, tag)
    total_before = owner.get("/api/games", params={"limit": 1}).json()["total"]

    r = owner.post(
        "/api/backup/restore",
        files={"file": ("not-a-backup.zip", io.BytesIO(b"this is not a zip"), "application/zip")},
    )
    assert r.status_code >= 400, "a corrupt file was accepted"
    assert _titles(owner, tag) == before, "a rejected restore still changed the database"
    assert owner.get("/api/games", params={"limit": 1}).json()["total"] == total_before, \
        "a rejected restore changed rows it never reported"
