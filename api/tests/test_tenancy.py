"""Can one person see another person's collection?

Thirteen routers is thirteen chances to forget a filter, and a missed one is
invisible from the inside: everything looks right until the day somebody else's
Charizard turns up in your grid. So this doesn't test a filter, it tests the
property — two real accounts, through the real API, and nothing of one may
appear anywhere in the other's answers.

Written before the sweep it checks, on purpose. A test written afterwards
tends to describe what the code does rather than what it should.

    docker compose -f compose.dev.yaml exec -e AUTH_MODE=multi api \\
        python -m pytest tests/test_tenancy.py -v

It needs AUTH_MODE=multi and an install nobody has claimed yet.
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")

# every collection that lists things somebody owns
MODULES = {
    "cards": "/api/cards",
    "games": "/api/games",
    "movies": "/api/movies",
    "books": "/api/books",
    "records": "/api/records",
    "lego": "/api/lego",
    "comics": "/api/comics",
}
# how to create one, per module — the smallest body each endpoint accepts
CREATE = {
    "cards": ("/api/cards", {"title": "T", "card_number": "1"}),
    "games": ("/api/games", {"title": "T"}),
    "movies": ("/api/movies", {"title": "T"}),
    "books": ("/api/books", {"title": "T"}),
    "records": ("/api/records", {"title": "T"}),
    "lego": ("/api/lego", {"title": "T", "set_number": "0001-1"}),
    "comics": ("/api/comics", {"title": "T", "series": "T"}),
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=30)


@pytest.fixture(scope="module")
def people(owner):
    """The owner, and somebody they invited."""
    me = owner.get("/api/auth/me").json()
    if not me["multi_user"]:
        pytest.skip("needs AUTH_MODE=multi")

    bob_email = f"bob-{uuid.uuid4().hex[:8]}@example.com"
    owner.post(
        "/api/auth/users",
        json={"email": bob_email, "password": "bob-password-2"},
    ).raise_for_status()

    bob = _client()
    bob.post(
        "/api/auth/login", json={"email": bob_email, "password": "bob-password-2"}
    ).raise_for_status()

    yield owner, bob
    bob.close()


def _own(client: httpx.Client, module: str, title: str) -> int:
    path, body = CREATE[module]
    item = client.post(path, json={**body, "title": title}).json()
    client.post(f"/api/items/{item['id']}/owned", json={"condition": "NM"}).raise_for_status()
    return item["id"]


@pytest.mark.parametrize("module", sorted(MODULES))
def test_one_persons_shelf_is_their_own(people, module):
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    mine = _own(alice, module, f"Alice {module} {tag}")
    theirs = _own(bob, module, f"Bob {module} {tag}")

    listed = {i["id"] for i in alice.get(MODULES[module], params={"limit": 100}).json()["items"]}
    assert mine in listed, f"{module}: Alice cannot see her own item"
    assert theirs not in listed, f"{module}: Alice can see Bob's item"


def test_a_shared_catalogue_entry_does_not_share_its_copies(people):
    """The sharpest case, and the one a list-level filter alone misses.

    Two people owning the same game is normal and the catalogue row is
    deliberately shared. What must not be shared is the row saying how worn
    *your* copy is, what you paid, or the cert number on your slab.
    """
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    item = alice.post("/api/games", json={"title": f"Shared {tag}"}).json()["id"]
    alice.post(f"/api/items/{item}/owned", json={"condition": "NM", "notes": "alice-secret"})
    bob.post(f"/api/items/{item}/owned", json={"condition": "DMG", "notes": "bob-secret"})

    for who, other in ((alice, "bob-secret"), (bob, "alice-secret")):
        row = next(i for i in who.get("/api/games", params={"limit": 100}).json()["items"]
                   if i["id"] == item)
        assert len(row["owned"]) == 1, f"sees {len(row['owned'])} copies, should see 1"
        assert other not in str(row["owned"]), f"can read the other person's copy ({other})"


def test_the_wanted_list_is_private(people):
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    item = alice.post("/api/games", json={"title": f"Wanted {tag}"}).json()["id"]
    alice.post(f"/api/items/{item}/wanted", json={})

    assert item in {r["item_id"] for r in alice.get("/api/wanted").json()}
    assert item not in {r["item_id"] for r in bob.get("/api/wanted").json()}


def test_two_people_may_want_the_same_thing(people):
    """`wanted.item_id` was UNIQUE, so the second person got a 500."""
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    item = alice.post("/api/games", json={"title": f"Both want {tag}"}).json()["id"]
    assert alice.post(f"/api/items/{item}/wanted", json={}).status_code < 400
    assert bob.post(f"/api/items/{item}/wanted", json={}).status_code < 400


def test_counts_are_per_person(people):
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    _own(alice, "movies", f"Counted {tag}")
    a = alice.get("/api/stats").json()["movies"]["owned"]
    b = bob.get("/api/stats").json()["movies"]["owned"]
    _own(alice, "movies", f"Counted again {tag}")
    assert alice.get("/api/stats").json()["movies"]["owned"] == a + 1
    assert bob.get("/api/stats").json()["movies"]["owned"] == b, "Bob's count moved when Alice added"


def test_the_binder_is_one_persons_binder(people):
    """Missed by the first pass of this file, and a real leak because of it.

    The Pokedex asks for cards flagged in_binder, and that flag lives on a
    copy — so without a filter it returned everybody's binder, merged. Added
    here after it was found by reading the query rather than by running the
    suite, which is the argument for the suite covering every list the app
    draws rather than the ones that came to mind.
    """
    alice, bob = people
    tag = uuid.uuid4().hex[:8]
    card = alice.post(
        "/api/cards", json={"title": f"Binder {tag}", "card_number": "1", "national_dex_no": 493}
    ).json()
    alice.post(
        f"/api/items/{card['id']}/owned", json={"condition": "NM", "in_binder": True}
    ).raise_for_status()

    def occupied(client):
        entries = client.get("/api/cards/pokedex").json()["entries"]
        return {e["dex_no"] for e in entries if e.get("card")}

    assert 493 in occupied(alice), "Alice cannot see her own binder card"
    assert 493 not in occupied(bob), "Bob can see Alice's binder"


def test_a_stranger_gets_nothing():
    with _client() as anon:
        if not anon.get("/api/auth/me").json()["multi_user"]:
            pytest.skip("needs AUTH_MODE=multi")
        for path in ("/api/games", "/api/wanted", "/api/stats", "/api/settings"):
            assert anon.get(path).status_code == 401, f"{path} answered a stranger"
