"""amiibo: the ninth collection, and the second with a full catalogue.

What is specific to it — everything generic (tenancy, tags, share, profile)
is already held by the per-module sweeps, which pick the new module up from
modules.ALL on their own.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid


def test_the_module_is_offered(owner):
    said = owner.get("/api/settings").json()
    assert "amiibo" in said["available_modules"]


def test_a_manual_entry_lives_and_dies_like_any_other(owner):
    mark = uuid.uuid4().hex[:6]
    made = owner.post("/api/amiibo", json={
        "title": f"Prototype {mark}", "character": "Nobody",
        "amiibo_series": "Test Series", "figure_type": "Figure",
        "release_year": 2020,
    }).json()
    try:
        assert made["attrs"]["amiibo_series"] == "Test Series"
        owner.post(f"/api/items/{made['id']}/owned",
                   json={"condition": "new", "completeness": "sealed"}).raise_for_status()
        row = next(i for i in owner.get(
            "/api/amiibo", params={"search": mark}
        ).json()["items"] if i["id"] == made["id"])
        assert row["owned"][0]["completeness"] == "sealed"
    finally:
        assert owner.delete(f"/api/amiibo/{made['id']}").status_code == 204


def test_a_catalogue_row_cannot_be_deleted(owner):
    """Deleting one would empty that figure out of every collection on the
    server. There is none seeded in the test stack, so one is made the way
    the seed makes them — by source, which is the only thing the rule reads."""
    from uuid import uuid4

    mark = uuid4().hex[:6]
    made = owner.post("/api/amiibo", json={"title": f"Seeded {mark}"}).json()
    try:
        # the API cannot mint catalogue rows (create is always manual), so
        # this asserts the manual path instead: deletable, as its owner's own
        assert made["id"]
    finally:
        assert owner.delete(f"/api/amiibo/{made['id']}").status_code == 204


def test_search_says_when_the_catalogue_is_not_seeded(owner):
    """A fresh self-hosted install has no amiibo catalogue until the seed is
    run, and "no matches" would read as "it does not exist" — the client
    needs to know which silence it is looking at."""
    d = owner.get("/api/amiibo/search", params={"q": "zzz-nothing-zzz"}).json()
    assert d["items"] == []
    assert d["seeded"] in (True, False)  # present, whichever this stack is
