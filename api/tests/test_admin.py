"""Can anybody but an admin see the admin panel?

That is the only question here that really matters. The panel reports how
many accounts exist, what everybody owns and who has paid — a page that
leaked any of that to an ordinary account would be worse than not having it.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
OPEN = os.environ.get("LOOT_OPEN_URL")

ADMIN_PATHS = ["/api/admin/stats", "/api/admin/users"]


def test_a_stranger_is_refused():
    """Signed out entirely."""
    for path in ADMIN_PATHS:
        r = httpx.get(f"{BASE}{path}", timeout=60)
        assert r.status_code in (401, 403), f"{path} answered {r.status_code} to nobody"


@pytest.mark.skipif(not OPEN, reason="no open-signup API configured")
def test_an_ordinary_account_is_refused():
    """Signed in, but not an admin — the case a guard is actually for."""
    c = httpx.Client(base_url=OPEN, timeout=60)
    try:
        c.post(
            "/api/auth/signup",
            json={
                "email": f"nosy-{uuid.uuid4().hex[:8]}@example.com",
                "password": "a-real-password-1",
                "accept_terms": True,
                    "screen_name": f"t{uuid.uuid4().hex[:10]}",
            },
        ).raise_for_status()

        for path in ADMIN_PATHS:
            r = c.get(path)
            assert r.status_code == 403, f"{path} answered {r.status_code} to a normal account"

        # and it cannot hand itself a plan
        me = c.get("/api/auth/me").json()["user"]["id"]
        r = c.put(f"/api/admin/users/{me}/plan", json={"plan": "supporter"})
        assert r.status_code == 403, "an ordinary account promoted itself"
    finally:
        c.close()


def test_an_admin_sees_the_numbers(owner):
    s = owner.get("/api/admin/stats")
    assert s.status_code == 200
    body = s.json()

    for section in ("accounts", "catalogue", "collections", "storage", "barcodes", "install"):
        assert section in body, f"stats lost its {section}"
    assert body["accounts"]["total"] >= 1
    assert isinstance(body["storage"]["photos_bytes"], int)


def test_the_list_says_who_has_paid(owner):
    rows = owner.get("/api/admin/users")
    assert rows.status_code == 200
    users = rows.json()
    assert users, "no accounts at all"
    for u in users:
        assert set(("id", "plan", "subscribed", "items")) <= set(u)
    assert any(u["is_admin"] for u in users), "nobody is an admin, which cannot be"


def test_it_reports_no_activity_about_anybody(owner):
    """A deliberate absence. The operator needs counts, not a record of what
    each person has been doing with the collection they trusted here."""
    body = owner.get("/api/admin/stats").json()
    flat = str(body).lower()
    for leak in ("last_seen", "last_login", "ip", "user_agent"):
        assert leak not in flat, f"the panel started reporting {leak}"


@pytest.fixture
def somebody(owner):
    """A non-admin account of this test's own, cleaned up afterwards.

    Made rather than borrowed: this stack is invite-only and can legitimately
    hold nothing but the owner, and a test that skips itself on the install
    it most needs to cover is not a test.
    """
    email = f"member-{uuid.uuid4().hex[:8]}@example.com"
    made = owner.post(
        "/api/auth/users",
        json={"email": email, "password": "a-real-password-1", "is_admin": False},
    )
    if made.status_code != 201:
        pytest.skip(f"could not create an account to test with ({made.status_code})")
    uid = made.json()["id"]
    yield uid
    owner.delete(f"/api/auth/users/{uid}")


def test_a_plan_can_be_granted_and_taken_back(owner, somebody):
    """The way plans are set until Stripe exists, and the way they are fixed
    when a payment goes strange afterwards."""
    given = owner.put(f"/api/admin/users/{somebody}/plan", json={"plan": "supporter"})
    given.raise_for_status()
    assert given.json()["subscribed"] is True
    assert given.json()["plan_until"] is None, "a hand-granted plan should not expire"

    taken = owner.put(f"/api/admin/users/{somebody}/plan", json={"plan": "free"})
    taken.raise_for_status()
    assert taken.json()["subscribed"] is False


def test_a_granted_plan_shows_up_in_the_list(owner, somebody):
    owner.put(f"/api/admin/users/{somebody}/plan", json={"plan": "supporter"}).raise_for_status()
    row = next(u for u in owner.get("/api/admin/users").json() if u["id"] == somebody)
    assert row["plan"] == "supporter" and row["subscribed"] is True


def test_a_nonsense_plan_is_refused(owner):
    users = owner.get("/api/admin/users").json()
    target = next((u for u in users if not u["is_admin"]), users[0])
    r = owner.put(f"/api/admin/users/{target['id']}/plan", json={"plan": "vip"})
    assert r.status_code == 422
