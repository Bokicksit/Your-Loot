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
    assert b.delete("/api/sync/mirror").status_code == 403

    # and the one question a sender asks before it builds the zip
    r = b.post("/api/backup/mine/have", json={"names": ["nope.png", "../etc/passwd"]})
    assert r.status_code == 200
    assert r.json()["missing"] == ["nope.png"]   # the climb-out is not a file, so not "missing"

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


# ------------------------------------------------------------ the mirror

@needs_open
def test_a_collection_that_arrives_on_a_sync_token_marks_the_account_a_mirror(owner, receiver):
    there, tok = receiver
    assert there.get("/api/settings").json()["mirror"] is None
    owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"]}).raise_for_status()
    owner.post("/api/sync/now").raise_for_status()

    m = there.get("/api/settings").json()["mirror"]
    assert m and m["at"] and m["source"]      # the test API has no public URL, so "your home server"

    # stopping clears the mark and revokes the tokens, so the old source is refused
    r = there.delete("/api/sync/mirror")
    assert r.status_code == 200 and r.json()["revoked_tokens"] == 1
    assert there.get("/api/settings").json()["mirror"] is None
    assert owner.post("/api/sync/now").status_code == 502
    owner.delete("/api/sync")


@needs_open
def test_a_restore_of_your_own_file_does_not_make_you_a_mirror(receiver):
    """Same endpoint, cookie rather than sync token: that is a person loading
    their own backup, and nothing about their account changes."""
    c, _ = receiver
    blob = c.get("/api/backup/mine").content
    c.post("/api/backup/mine", files={"file": ("c.zip", blob, "application/zip")},
           data={"confirm": "RESTORE"}).raise_for_status()
    assert c.get("/api/settings").json()["mirror"] is None


def test_the_mirror_mark_never_travels():
    from app import mine

    assert mine.MIRROR_KEYS <= mine.LOCAL_ONLY


# ----------------------------------------------------- only new photos go

def test_only_the_photos_the_other_side_lacks_are_packed(tmp_path, monkeypatch):
    from app import mine

    monkeypatch.setattr(mine.cfg, "image_dir", str(tmp_path))
    (tmp_path / "a.jpg").write_bytes(b"A")
    (tmp_path / "b.jpg").write_bytes(b"B")
    payload = {"items": [{"image_url": "/images/a.jpg"}, {"image_url": "/images/b.jpg"}],
               "binders": [], "owned": [], "wanted": [], "tags": [], "settings": []}

    everything = zipfile.ZipFile(io.BytesIO(mine.to_zip(None, None, payload=payload)))
    assert {n for n in everything.namelist() if n.startswith("images/")} == {"images/a.jpg", "images/b.jpg"}

    some = zipfile.ZipFile(io.BytesIO(mine.to_zip(None, None, payload=payload, only_images={"b.jpg"})))
    assert {n for n in some.namelist() if n.startswith("images/")} == {"images/b.jpg"}

    none = zipfile.ZipFile(io.BytesIO(mine.to_zip(None, None, payload=payload, only_images=set())))
    assert not [n for n in none.namelist() if n.startswith("images/")]

    assert mine.images_missing(["a.jpg", "zzz.jpg", "../x", ".hidden"]) == ["zzz.jpg"]


@needs_open
def test_the_second_send_carries_no_photos_it_already_sent(owner, receiver):
    """Provable without photos: the receiver reports how many images it wrote,
    and a second send of an unchanged collection must write none."""
    there, tok = receiver
    owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"]}).raise_for_status()
    first = owner.post("/api/sync/now").json()["result"]
    second = owner.post("/api/sync/now").json()["result"]
    assert second["images"] == 0
    assert second["copies"] == first["copies"]
    owner.delete("/api/sync")


# ------------------------------------------------ send it after a change

def test_a_change_waits_out_the_debounce_then_is_due(monkeypatch):
    from app.routers import sync

    now = [10_000.0]
    monkeypatch.setattr(sync.time, "monotonic", lambda: now[0])
    sync._pending.clear()
    sync.notify_change(7)
    assert sync._changes_due() == []
    now[0] += sync.DEBOUNCE - 1
    assert sync._changes_due() == []
    sync.notify_change(7)                      # another change resets the wait
    now[0] += sync.DEBOUNCE - 1
    assert sync._changes_due() == []
    now[0] += 2
    assert sync._changes_due() == [7]
    sync._pending.clear()


def test_a_write_to_a_collection_marks_its_owner(owner):
    """Filing something is what makes an account pending — seen from the
    outside as the status the settings screen reads."""
    owner.put("/api/sync", json={"url": OPEN_INSIDE or "http://api-open:8000",
                                 "token": "not-a-real-token", "on_change": True}).raise_for_status()
    assert owner.get("/api/sync").json()["pending"] is False   # saving settings is not a change
    made = owner.post("/api/cards", json={"title": "Sync Probe"}).json()
    owner.post(f"/api/items/{made['id']}/owned", json={"quantity": 1}).raise_for_status()
    st = owner.get("/api/sync").json()
    assert st["on_change"] is True and st["pending"] is True
    owner.delete(f"/api/cards/{made['id']}")
    owner.delete("/api/sync")
    assert owner.get("/api/sync").json()["pending"] is False


@needs_open
def test_the_same_collection_can_land_in_two_accounts_on_one_server(owner, receiver):
    """The failure that found the per-server unique index: a binder's uid
    travels with it, so two mirrors of one collection carry the same uids,
    and both have to be allowed to exist."""
    there, tok = receiver
    other = httpx.Client(base_url=OPEN, timeout=120)
    other.post("/api/auth/signup", json={
        "email": f"second-{uuid.uuid4().hex[:8]}@example.com", "password": PASSWORD,
        "accept_terms": True, "screen_name": f"s{uuid.uuid4().hex[:8]}",
    }).raise_for_status()
    tok2 = other.post("/api/auth/tokens", json={"name": "home", "scope": "sync"}).json()

    for t in (tok, tok2):
        owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": t["token"]}).raise_for_status()
        r = owner.post("/api/sync/now")
        assert r.status_code == 200, r.text
    mine_names = {b["name"] for b in owner.get("/api/binders").json()["binders"]}
    assert {b["name"] for b in there.get("/api/binders").json()["binders"]} >= mine_names
    assert {b["name"] for b in other.get("/api/binders").json()["binders"]} >= mine_names
    owner.delete("/api/sync")
    other.close()


# ------------------------------------------------- why a send failed

def test_the_failure_message_names_the_cause():
    """Every way a send can fail arrives as one 502, so this string is the
    whole diagnosis — and "Internal Server Error" passed through from the far
    side is not one."""
    from app.routers.sync import explain

    class R:
        def __init__(self, code, body=None):
            self.status_code = code
            self._body = body
        def json(self):
            if self._body is None:
                raise ValueError("not json")
            return self._body

    MB = 1024 * 1024
    url = "https://yourloot.app"

    assert "token was refused" in explain(R(401), url, MB)
    assert "token was refused" in explain(R(403), url, MB)
    assert "not a Your Loot" in explain(R(404), url, MB)

    too_big = explain(R(413), url, 140 * MB)
    assert "too large" in too_big and "140 MB" in too_big and "100 MB" in too_big

    assert "rate-limiting" in explain(R(429), url, MB)

    # the receiver's own words for a refusal it wrote for a person
    plan = explain(R(400, {"detail": "This collection has 900 cards and the plan on this account allows 300."}), url, MB)
    assert "900 cards" in plan and "allows 300" in plan

    for code in (502, 503, 504, 522, 524):
        out = explain(R(code), url, 80 * MB)
        assert "did not answer in time" in out and str(code) in out and "80 MB" in out

    # the case that started this: a bare 500 from the far side must still say
    # where the fault is and that nothing here changed
    dull = explain(R(500, {"detail": "Internal Server Error"}), url, MB)
    assert "that server hit an error" in dull and "500" in dull and "nothing here was changed" in dull

    # a body that is not JSON at all — a proxy's HTML error page
    assert "418" in explain(R(418), url, MB)


@needs_open
def test_a_receiver_that_already_has_a_pokedex_still_accepts_a_collection(owner, receiver):
    """The bug this file did not catch until it happened for real.

    Every account grows a Pokédex the first time it files a card, with a uid
    of its own. The collection arriving carries the *sender's* uid for its
    Pokédex, which matches nothing here — so a second one was created, and
    "one Pokédex each" is a database constraint, so the whole load failed
    with a 500. The tests passed only because a freshly signed-up receiver
    had never touched a binder.
    """
    there, tok = receiver
    # national_dex_no is a field of the card, not of its attrs block — and it
    # is what gives the card a Pokédex slot, which is what makes the binder
    made = there.post("/api/cards", json={"title": "Pikachu", "national_dex_no": 25}).json()
    there.post(f"/api/items/{made['id']}/owned", json={"quantity": 1}).raise_for_status()
    before = there.get("/api/binders").json()["binders"]
    dex_here = [b for b in before if b["kind"] == "dex"]
    assert len(dex_here) == 1, "the receiver should have made its own Pokédex by now"

    owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"]}).raise_for_status()
    r = owner.post("/api/sync/now")
    assert r.status_code == 200, r.text

    after = there.get("/api/binders").json()["binders"]
    dex_after = [b for b in after if b["kind"] == "dex"]
    assert len(dex_after) == 1, "a second Pokédex was made instead of the first being reused"
    # and it is the same row, so a link anybody had to it still works
    assert dex_after[0]["id"] == dex_here[0]["id"]

    # a second send matches on the uid it adopted and is still one Pokédex
    assert owner.post("/api/sync/now").status_code == 200
    assert len([b for b in there.get("/api/binders").json()["binders"] if b["kind"] == "dex"]) == 1
    owner.delete("/api/sync")


@needs_open
def test_a_binder_of_the_same_name_is_reused_rather_than_doubled(owner, receiver):
    """The same rule below the Pokédex: a custom binder is the one here with
    that name. Nothing in the database forbids two, so this one duplicated
    silently rather than failing — which is worse, not better.

    (A set binder matches on its set the same way. It cannot be tested on this
    stack, which seeds no catalogue and so refuses to make one.)
    """
    there, tok = receiver
    theirs = there.post("/api/binders", json={"name": "Trade", "kind": "custom", "pages": 1}).json()
    mine_b = owner.post("/api/binders", json={"name": "Trade", "kind": "custom", "pages": 1}).json()

    owner.put("/api/sync", json={"url": OPEN_INSIDE, "token": tok["token"]}).raise_for_status()
    assert owner.post("/api/sync/now").status_code == 200

    rows = [b for b in there.get("/api/binders").json()["binders"] if b["name"] == "Trade"]
    assert len(rows) == 1, "a second binder of the same name was made"
    assert rows[0]["id"] == theirs["id"]   # the row held, so a link to it holds
    owner.delete(f"/api/binders/{mine_b['id']}")
    owner.delete("/api/sync")
