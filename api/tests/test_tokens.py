"""Does a bearer token let in exactly one person, and only while it lasts?

A token is a password that travels in a header, so the questions are the same
ones the cookie already has to answer — whose is it, can it be withdrawn, and
can it see anything that isn't theirs — plus one a cookie never faces: the
value exists in the clear only once, and if the server can show it again then
a copy of the database is a copy of everybody's access.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def _bare() -> httpx.Client:
    """A client with no cookies at all — the state a phone app is in."""
    return httpx.Client(base_url=BASE, timeout=30)


def _mint(client: httpx.Client, name: str) -> tuple[int, str]:
    r = client.post("/api/auth/tokens", json={"name": name})
    r.raise_for_status()
    d = r.json()
    return d["id"], d["token"]


def test_a_token_gets_in_without_a_cookie(owner):
    """The whole point: no session, no cookie, still recognised."""
    _, raw = _mint(owner, f"phone {uuid.uuid4().hex[:6]}")
    with _bare() as c:
        r = c.get("/api/auth/me", headers={"Authorization": f"bearer {raw}"})
        assert r.status_code == 200, r.text
        assert c.cookies.keys() == [] or "uid" not in str(c.cookies)


def test_the_value_is_shown_once_and_never_again(owner):
    """Only a hash is stored, so nothing can hand it back. If this ever fails,
    a copy of the table has become a copy of everyone's access."""
    tid, raw = _mint(owner, f"once {uuid.uuid4().hex[:6]}")
    listed = owner.get("/api/auth/tokens").json()["tokens"]
    mine = next(t for t in listed if t["id"] == tid)
    assert raw not in str(listed), "the raw token came back from the server"
    assert mine["prefix"] and mine["prefix"] in raw, "prefix should identify it"
    assert len(mine["prefix"]) < len(raw), "the prefix is not the whole token"


def test_a_revoked_token_stops_working(owner):
    tid, raw = _mint(owner, f"revoke {uuid.uuid4().hex[:6]}")
    with _bare() as c:
        assert c.get("/api/auth/me", headers={"Authorization": f"bearer {raw}"}).status_code == 200
    assert owner.delete(f"/api/auth/tokens/{tid}").status_code == 204
    with _bare() as c:
        r = c.get("/api/games", headers={"Authorization": f"bearer {raw}"}, params={"limit": 1})
        assert r.status_code == 401, f"a revoked token still worked ({r.status_code})"


def test_a_made_up_token_is_not_somebody(owner):
    """It must fall through to the ordinary answer, not become anyone."""
    with _bare() as c:
        r = c.get("/api/games", headers={"Authorization": "bearer ylt_not-a-real-token"},
                  params={"limit": 1})
        # 401 in any install that has a login; an open single-user install
        # answers as the owner, which is what it does for every request
        assert r.status_code in (200, 401)


@pytest.fixture(scope="module")
def people(owner):
    me = owner.get("/api/auth/me").json()
    if not me["multi_user"]:
        pytest.skip("needs AUTH_MODE=multi")
    email = f"tokbob-{uuid.uuid4().hex[:8]}@example.com"
    owner.post("/api/auth/users", json={"email": email, "password": "bob-password-2"}).raise_for_status()
    bob = _bare()
    bob.post("/api/auth/login", json={"email": email, "password": "bob-password-2"}).raise_for_status()
    yield owner, bob
    bob.close()


def test_a_token_sees_only_its_owners_shelf(people):
    """The sharp one. A token is an account, not a skeleton key."""
    alice, bob = people
    mark = uuid.uuid4().hex[:8]
    hers = alice.post("/api/games", json={"title": f"Alice {mark}"}).json()["id"]
    alice.post(f"/api/items/{hers}/owned", json={"condition": "NM"}).raise_for_status()
    his = bob.post("/api/games", json={"title": f"Bob {mark}"}).json()["id"]
    bob.post(f"/api/items/{his}/owned", json={"condition": "NM"}).raise_for_status()

    _, raw = _mint(bob, f"bobs phone {mark}")
    with _bare() as c:
        seen = c.get("/api/games", headers={"Authorization": f"bearer {raw}"},
                     params={"limit": 200}).json()["items"]
    ids = {i["id"] for i in seen}
    assert his in ids, "Bob's token cannot see Bob's own game"
    assert hers not in ids, "Bob's token can see Alice's game"


def test_you_cannot_revoke_somebody_elses_token(people):
    alice, bob = people
    tid, _ = _mint(alice, f"alice {uuid.uuid4().hex[:6]}")
    assert bob.delete(f"/api/auth/tokens/{tid}").status_code == 404
    # and it still works for her
    assert any(t["id"] == tid and t["revoked_at"] is None
               for t in alice.get("/api/auth/tokens").json()["tokens"])


def test_bobs_token_is_not_in_alices_list(people):
    alice, bob = people
    tid, _ = _mint(bob, f"bob {uuid.uuid4().hex[:6]}")
    assert all(t["id"] != tid for t in alice.get("/api/auth/tokens").json()["tokens"])
