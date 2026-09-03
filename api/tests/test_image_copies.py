"""A kept copy of every linked picture, for when the link breaks.

The rule about whose items earn one, the naming that makes two items with
one picture one file, the record of a failure so a dead link is not retried
every hour forever, and the route the page falls back to — all provable
without touching the network, by handing copy_one a fetcher that returns
bytes. One test does reach a real CDN, because a copier that has never
copied anything real is a story.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, "/app")

from app import copies, plans  # noqa: E402

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


class U:
    def __init__(self, plan="free", admin=False, until=None):
        self.plan, self.is_admin, self.plan_until = plan, admin, until


# ------------------------------------------------------------- who earns one

def test_everybody_earns_copies_where_nothing_is_sold(monkeypatch):
    monkeypatch.setattr(plans.settings, "paid_modules", "")
    from app import limits
    monkeypatch.setattr(limits.settings, "free_card_limit", 0)
    monkeypatch.setattr(limits.settings, "free_dex_limit", 0)
    monkeypatch.setattr(limits.settings, "free_binder_limit", 0)
    assert plans.keeps_copies(U()) is True


def test_only_supporters_and_admins_earn_copies_where_something_is_sold(monkeypatch):
    monkeypatch.setattr(plans.settings, "paid_modules", "records")
    assert plans.keeps_copies(U()) is False
    assert plans.keeps_copies(U(plan="supporter")) is True
    assert plans.keeps_copies(U(admin=True)) is True


# -------------------------------------------------------------- the copying

@pytest.fixture
def kept(tmp_path, monkeypatch):
    monkeypatch.setattr(copies.settings, "image_dir", str(tmp_path))
    return tmp_path


def _item(image_url, item_id=1):
    return type("I", (), {"id": item_id, "image_url": image_url})()


class FakeDB:
    """Enough of a session for copy_one: get, add, commit."""
    def __init__(self):
        self.rows = {}
        self.commits = 0
    def get(self, model, key):
        return self.rows.get(key)
    def add(self, row):
        self.rows[row.item_id] = row
    def commit(self):
        self.commits += 1


def test_a_copy_is_named_by_its_content_so_one_picture_is_one_file(kept):
    db = FakeDB()
    png = b"\\x89PNG fake bytes"
    a = copies.copy_one(db, _item("https://cdn.example/a.png", 1), get=lambda u: (png, ".png"))
    b = copies.copy_one(db, _item("https://cdn.example/b.png", 2), get=lambda u: (png, ".png"))
    assert a.name == b.name and a.name.startswith("copy-") and a.name.endswith(".png")
    assert len(list(kept.iterdir())) == 1          # two items, one file
    assert a.bytes == len(png) and a.fetched_at and a.failed_at is None


def test_a_dead_link_is_recorded_not_retried_forever(kept):
    db = FakeDB()
    def dead(url):
        raise httpx.HTTPError("gone")
    row = copies.copy_one(db, _item("https://cdn.example/gone.png", 3), get=dead)
    assert row.name is None and row.failed_at is not None and "gone" in (row.error or "")
    assert not list(kept.iterdir())
    # and a later success clears the failure
    row = copies.copy_one(db, _item("https://cdn.example/gone.png", 3), get=lambda u: (b"ok", ".jpg"))
    assert row.name and row.failed_at is None and row.error is None


def test_path_for_answers_only_when_the_file_is_really_there(kept):
    db = FakeDB()
    copies.copy_one(db, _item("https://cdn.example/x.png", 9), get=lambda u: (b"xx", ".png"))
    assert copies.path_for(db, 9) is not None
    for f in kept.iterdir():
        f.unlink()                                 # the disk lost it
    assert copies.path_for(db, 9) is None
    assert copies.path_for(db, 12345) is None      # never had one


# ------------------------------------------------------------- the fallback

def test_the_fallback_route_is_public_and_404s_when_there_is_no_copy():
    r = httpx.get(f"{BASE}/api/images/fallback/999999", timeout=30)
    assert r.status_code == 404
    assert r.headers.get("cache-control") == "no-store"


def test_a_real_linked_picture_is_copied_and_then_served(owner):
    """End to end against a real CDN: an owned card whose art is a link gets
    a copy on the hourly pass (run here by hand), and the fallback route
    serves it, cacheable."""
    url = "https://assets.tcgdex.net/en/base/base1/4/low.webp"
    item = owner.post("/api/cards", json={"title": f"Kept {uuid.uuid4().hex[:6]}", "image_url": url}).json()
    owner.post(f"/api/items/{item['id']}/owned", json={"quantity": 1}).raise_for_status()

    before = owner.get("/api/admin/image-copies").json()
    assert before["on"] is True
    tally = owner.post("/api/admin/image-copies/run").json()
    assert tally["tried"] >= 1 and tally["kept"] >= 1, tally

    r = httpx.get(f"{BASE}/api/images/fallback/{item['id']}", timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("image/")
    assert "public" in r.headers.get("cache-control", "")
    assert len(r.content) > 1000

    after = owner.get("/api/admin/image-copies").json()
    assert after["kept"] >= before["kept"] + 1 and after["bytes"] > before["bytes"]

    # a second pass keeps nothing new: this item is done and stays done
    again = owner.post("/api/admin/image-copies/run").json()
    assert again["kept"] == 0, again
    owner.delete(f"/api/cards/{item['id']}")
