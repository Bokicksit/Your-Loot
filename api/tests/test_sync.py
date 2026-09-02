"""A collection sent from one install to an account on another.

The whole feature is the "restore my collection" endpoint reached from a
different server with a narrow token, so what needs proving is the narrow
part and the two things a repeated restore has to get right that a one-off
never did: binders keeping their ids, and a plan not being quietly exceeded.

The push itself is tested for real, between two of the APIs in the test
stack — the invite-only one sends, a fresh account on the open-signup one
receives — over the compose network, which is why that API allows a private
target (SYNC_ALLOW_PRIVATE in compose.test.yaml).

    docker compose -f compose.test.yaml run --rm tests
"""

import io
import json
import os
import sys
import uuid
import zipfile

import httpx
import pytest

sys.path.insert(0, "/app")

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
OPEN = os.environ.get("LOOT_OPEN_URL")
# how the sending API reaches the receiving one, from inside the network
OPEN_INSIDE = "http://api-open:8000"
PASSWORD = "a-perfectly-fine-password-1"
OPEN_OWNER_EMAIL = "open-owner@example.com"
OWNER_PASSWORD = "the-owner-password-1"

needs_open = pytest.mark.skipif(not OPEN, reason="no open-signup API configured")


@pytest.fixture(scope="module", autouse=True)
def owner_of_open():
    """Claim account 1 on the open API before any signup does — the same
    guard test_accounts.py keeps, for the same reason."""
    if not OPEN:
        yield
        return
    c = httpx.Client(base_url=OPEN, timeout=60)
    if c.get("/api/auth/me").json().get("needs_setup"):
        c.post("/api/auth/setup",
               json={"email": OPEN_OWNER_EMAIL, "password": OWNER_PASSWORD}).raise_for_status()
    c.close()
    yield


@pytest.fixture
def receiver():
    """A fresh account on the open API: its cookie client and a sync token."""
    c = httpx.Client(base_url=OPEN, timeout=120)
    email = f"mirror-{uuid.uuid4().hex[:10]}@example.com"
    c.post("/api/auth/signup", json={
        "email": email, "password": PASSWORD, "accept_terms": True,
        "screen_name": f"m{uuid.uuid4().hex[:10]}",
    }).raise_for_status()
    tok = c.post("/api/auth/tokens", json={"name": "home", "scope": "sync"}).json()
    yield c, tok
    c.close()


def bearer(token: str) -> httpx.Client:
    return httpx.Client(base_url=OPEN, timeout=120,
                        headers={"Authorization": f"bearer {token}"})


def rezip(raw: bytes, edit) -> bytes:
    """The same zip with its collection.json passed through `edit`."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    payload = json.loads(z.read("collection.json"))
    edit(payload)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as w:
        w.writestr("collection.json", json.dumps(payload))
        for n in names:
            if n != "collection.json":
                w.writestr(n, z.read(n))
    return out.getvalue()


# ------------------------------------------------------------ the narrow token

@needs_open
def test_a_sync_token_can_push_a_collection_and_nothing_else(receiver):
    c, tok = receiver
    assert tok["scope"] == "sync"
    b = bearer(tok["token"])

    # nothing that reads
    assert b.get("/api/cards").status_code == 403
    assert b.get("/api/binders").status_code == 403
    assert b.get("/api/backup/mine").status_code == 403       # the download
    # nothing that changes the account or widens access
    assert b.post("/api/auth/tokens", json={"name": "x"}).status_code == 403
    assert b.get("/api/sync").status_code == 403
    assert b.post("/api/sync/now").status_code == 403

    # the one thing it is for
    blob = c.get("/api/backup/mine").content
    r = b.post("/api/backup/mine", files={"file": ("c.zip", blob, "application/zip")},
               data={"confirm": "RESTORE"})
    assert r.status_code == 200, r.text


@needs_open
def test_a_full_token_is_still_the_account(receiver):
    c, _ = receiver
    tok = c.post("/api/auth/tokens", json={"name": "phone"}).json()
    assert tok["scope"] == "full"
    assert bearer(tok["token"]).get("/api/binders").status_code == 200


@needs_open
def test_a_revoked_sync_token_is_refused(receiver):
    c, tok = receiver
    c.delete(f"/api/auth/tokens/{tok['id']}").raise_for_status()
    blob = c.get("/api/backup/mine").content
    r = bearer(tok["token"]).post("/api/backup/mine",
                                 files={"file": ("c.zip", blob, "application/zip")},
                                 data={"confirm": "RESTORE"})
    assert r.status_code == 401


# ------------------------------------------------------ binders keep their ids

@needs_open
def test_a_restored_binder_keeps_its_id(receiver):
    """The link somebody was given to /u/name/binder/17 must survive the
    collection being loaded again — which, once it is mirrored nightly, is
    every night."""
    c, _ = receiver
    made = c.post("/api/binders", json={"name": "Trades", "kind": "custom", "pages": 1}).json()
    before = {b["id"]: b["name"] for b in c.get("/api/binders").json()["binders"]}
    assert made["id"] in before

    blob = c.get("/api/backup/mine").content
    for _ in range(2):
        r = c.post("/api/backup/mine", files={"file": ("c.zip", blob, "application/zip")},
                   data={"confirm": "RESTORE"})
        assert r.status_code == 200, r.text
    after = {b["id"]: b["name"] for b in c.get("/api/binders").json()["binders"]}
    assert after == before


@needs_open
def test_a_binder_gone_from_the_file_is_gone_from_the_account(receiver):
    c, _ = receiver
    keep = c.post("/api/binders", json={"name": "Keep", "kind": "custom", "pages": 1}).json()
    c.post("/api/binders", json={"name": "Gone", "kind": "custom", "pages": 1}).raise_for_status()
    blob = c.get("/api/backup/mine").content

    def drop_gone(p):
        p["binders"] = [b for b in p["binders"] if b.get("name") != "Gone"]

    r = c.post("/api/backup/mine", files={"file": ("c.zip", rezip(blob, drop_gone), "application/zip")},
               data={"confirm": "RESTORE"})
    assert r.status_code == 200, r.text
    names = {b["id"]: b["name"] for b in c.get("/api/binders").json()["binders"]}
    assert keep["id"] in names and "Gone" not in names.values()


@needs_open
def test_a_file_from_before_uids_still_finds_its_binders(receiver):
    """Older exports carry no uid. Set and dex binders are matched on what
    they are of and a custom one on its name, so a restore from such a file
    updates rather than duplicates."""
    c, _ = receiver
    made = c.post("/api/binders", json={"name": "Old Style", "kind": "custom", "pages": 1}).json()
    blob = c.get("/api/backup/mine").content

    def strip_uids(p):
        for b in p["binders"]:
            b.pop("uid", None)

    r = c.post("/api/backup/mine", files={"file": ("c.zip", rezip(blob, strip_uids), "application/zip")},
               data={"confirm": "RESTORE"})
    assert r.status_code == 200, r.text
    rows = c.get("/api/binders").json()["binders"]
    assert [b["id"] for b in rows if b["name"] == "Old Style"] == [made["id"]]


# ------------------------------------------------------------- the plan check

def test_a_collection_the_plan_cannot_hold_is_refused_before_anything_changes(monkeypatch):
    from app import limits, mine

    monkeypatch.setattr(limits.settings, "free_card_limit", 300)
    monkeypatch.setattr(limits.settings, "free_binder_limit", 1)
    free = type("U", (), {"plan": "free", "is_admin": False, "plan_until": None})()

    def payload(cards, binders):
        return {
            "items": [{"ref": i, "module": "cards"} for i in range(cards)]
                     + [{"ref": 10_000, "module": "games"}],
            "owned": [{"ref": i} for i in range(cards)] + [{"ref": 10_000}],
            "binders": [{"kind": "dex"}] + [{"kind": "custom"} for _ in range(binders)],
        }

    here = {"cards", "games"}
    mine.check_plan(payload(300, 1), free, here)          # exactly at the caps: fine
    with pytest.raises(mine.Refused, match="301 cards"):
        mine.check_plan(payload(301, 1), free, here)
    with pytest.raises(mine.Refused, match="2 binders"):
        mine.check_plan(payload(10, 2), free, here)
    # cards from a collection this install does not carry are not loaded, so
    # they are not counted either
    mine.check_plan(payload(301, 1), free, {"games"})


def test_the_plan_check_is_silent_where_nothing_is_limited(monkeypatch):
    from app import limits, mine

    monkeypatch.setattr(limits.settings, "free_card_limit", 0)
    monkeypatch.setattr(limits.settings, "free_binder_limit", 0)
    free = type("U", (), {"plan": "free", "is_admin": False, "plan_until": None})()
    mine.check_plan({"items": [{"ref": i, "module": "cards"} for i in range(5000)],
                     "owned": [{"ref": i} for i in range(5000)],
                     "binders": [{"kind": "custom"}] * 40}, free, {"cards"})


# ---------------------------------------------------------- where it may go

def test_the_target_address_is_checked_like_a_pasted_url(monkeypatch):
    from app.routers import sync

    monkeypatch.setattr(sync.settings, "sync_allow_private", False)
    with pytest.raises(sync.SyncError):
        sync.validate_url("ftp://yourloot.app")
    with pytest.raises(sync.SyncError):
        sync.validate_url("yourloot.app")           # no scheme
    with pytest.raises(sync.SyncError, match="SYNC_ALLOW_PRIVATE"):
        sync.validate_url("http://10.0.0.7:8000")   # a LAN address, refused by default
    monkeypatch.setattr(sync.settings, "sync_allow_private", True)
    assert sync.validate_url("http://10.0.0.7:8000/settings") == "http://10.0.0.7:8000"


# --------------------------------------------------------------- the push

@needs_open
def test_the_owner_here_can_mirror_into_an_account_over_there(owner, receiver):
    """End to end, across the compose network: this API's owner sends, a
    fresh account on the open API receives, and afterwards has the binders."""
    there, tok = receiver
    mine_binders = owner.get("/api/binders").json()["binders"]
    assert mine_binders, "the owner should at least have a Pokédex to send"

    r = owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"], "nightly": False})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["configured"] is True
    assert st["token_prefix"] == tok["token"][:8]
    assert "token" not in st  # the value never comes back

    r = owner.post("/api/sync/now")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["last_error"] is None
    assert out["last_at"]
    assert out["result"]["binders"] == len(mine_binders)

    theirs = there.get("/api/binders").json()["binders"]
    assert {b["name"] for b in theirs} >= {b["name"] for b in mine_binders}

    # stop, and the token is forgotten
    assert owner.delete("/api/sync").status_code == 204
    assert owner.get("/api/sync").json()["configured"] is False


@needs_open
def test_a_failed_send_is_recorded_not_swallowed(owner, receiver):
    there, tok = receiver
    there.delete(f"/api/auth/tokens/{tok['id']}").raise_for_status()   # revoked over there
    owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"]}).raise_for_status()
    r = owner.post("/api/sync/now")
    assert r.status_code == 502
    assert "refused" in r.json()["detail"]
    st = owner.get("/api/sync").json()
    assert st["last_error"] and "refused" in st["last_error"]
    owner.delete("/api/sync")


def test_the_settings_that_point_elsewhere_never_travel():
    """A mirror must not inherit the instruction to mirror itself onward."""
    from app import mine

    assert mine.SYNC_KEYS <= mine.LOCAL_ONLY
    assert "sync_token" in mine.LOCAL_ONLY
