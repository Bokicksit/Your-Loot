"""What ends up in a file you hand to somebody else?

Everywhere else in this app a mistake shows you the wrong thing. Here it shows
somebody else the wrong thing, and once the file is sent there is no taking it
back — no revoking a link, no patching a server. That asymmetry is the whole
reason this file exists.

So the first test is the one that matters: write a note, a tag, a serial
number and a grading certificate onto an item, share the collection, and check
that none of the four are anywhere in the bytes. It is a crude test on purpose.
It reads the file as text and searches it, because that is what the recipient
can do.

The rest guard the ways a share quietly stops being a share: it must need a
sign-in, it must not carry another account's rows, and every collection must
actually build — the sort keys and the row fields are written by hand, and the
first version offered to sort films by a year that films do not have.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")

SCOPES = [
    "records", "cards", "games", "hardware", "movies",
    "books", "lego", "comics", "wanted", "pokedex",
]


def _get(c: httpx.Client, scope: str, images: bool = False) -> httpx.Response:
    # images=false everywhere: this suite is about what the file says, and
    # fetching a thousand covers to prove it would make the run minutes long
    r = c.get(f"/api/share/{scope}", params={"images": str(images).lower()}, timeout=300)
    r.raise_for_status()
    return r


@pytest.mark.parametrize("scope", SCOPES)
def test_every_collection_builds(owner, scope):
    """The drift guard.

    Each collection names its own fields and its own sort options, by hand, in
    one block. Nothing but running it proves the names are real — three were
    wrong the first time, and each failed only when that collection was asked
    for.
    """
    r = _get(owner, scope)
    assert r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers["content-disposition"]
    body = r.text
    assert body.startswith("<!doctype html>")
    assert body.rstrip().endswith("</html>")
    # a share with no controls is a share whose script did not render
    assert '<div class="bar">' in body


def test_private_fields_never_leave(owner):
    """The one that matters.

    A note is where you write what you paid. A certificate number identifies a
    slab well enough to look up. Neither belongs in something you send to a
    stranger, and neither is visible in the app in a way that would remind you
    it was there.
    """
    mark = uuid.uuid4().hex[:10]
    secrets = {
        "note": f"paid-too-much-{mark}",
        "tag": f"tag{mark}",
        "serial": f"SN{mark}",
        "cert": f"CERT{mark}",
    }

    item = owner.post(
        "/api/games",
        json={"title": f"Share Test {mark}", "serial_number": secrets["serial"]},
    ).json()["id"]
    owner.patch(f"/api/games/{item}", json={"notes": secrets["note"]}).raise_for_status()
    owner.post(
        f"/api/items/{item}/owned",
        json={"condition": "NM", "grader": "PSA", "grade": "10",
              "cert_number": secrets["cert"]},
    ).raise_for_status()
    owner.put(
        f"/api/tags/item/{item}", json={"scope": "games", "names": [secrets["tag"]]}
    ).raise_for_status()

    body = _get(owner, "games").text
    try:
        # the item is there — otherwise this passes by finding nothing at all
        assert f"Share Test {mark}" in body
        # and the grade is, because that is a fact about the copy worth sharing
        assert "PSA 10" in body
        for field, value in secrets.items():
            assert value not in body, f"{field} leaked into the share"
    finally:
        owner.delete(f"/api/games/{item}")


def test_a_share_needs_a_sign_in():
    """Building somebody's collection is not a public act. The file may be
    passed around afterwards; producing it may not be."""
    with httpx.Client(base_url=BASE, timeout=30) as anon:
        r = anon.get("/api/share/records", params={"images": "false"})
        if r.status_code == 200:
            pytest.skip("this install has no lock on it")
        assert r.status_code == 401


def test_an_unknown_collection_is_a_404(owner):
    r = owner.get("/api/share/sneakers", params={"images": "false"})
    assert r.status_code == 404


def test_the_failed_cover_count_is_reported(owner):
    """A share missing half its pictures must say so. Asking for none is the
    one case where the answer is knowable without the network: zero."""
    r = _get(owner, "records", images=False)
    assert r.headers["x-share-images-failed"] == "0"


@pytest.fixture
def somebody_else(owner):
    """A second account, invited the way the app invites one."""
    if not owner.get("/api/auth/me").json().get("multi_user"):
        pytest.skip("single-user install: there is nobody else")
    email = f"share-other-{uuid.uuid4().hex[:8]}@example.com"
    owner.post(
        "/api/auth/users", json={"email": email, "password": "other-password-2"}
    ).raise_for_status()
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/api/auth/login", json={"email": email, "password": "other-password-2"}).raise_for_status()
    yield c
    c.close()


def test_nobody_elses_rows(owner, somebody_else):
    """Tenancy, from the outside. The share calls the same list functions the
    app does, which is the point — but that only helps while it keeps calling
    them, so this checks the property rather than the plumbing."""
    mark = uuid.uuid4().hex[:10]
    item = somebody_else.post("/api/records", json={"title": f"Theirs {mark}"}).json()["id"]
    somebody_else.post(f"/api/items/{item}/owned", json={"condition": "NM"})

    assert f"Theirs {mark}" not in _get(owner, "records").text


def test_a_shared_catalogue_row_shares_no_copies(owner, somebody_else):
    """The sharp case, and the one a list-level filter alone misses.

    Two people owning the same record is normal, and the catalogue row is
    deliberately shared between them. What must not travel is the row saying
    what shape *their* copy is in — which is exactly the field a share puts on
    the page.
    """
    mark = uuid.uuid4().hex[:10]
    item = owner.post("/api/records", json={"title": f"Both {mark}"}).json()["id"]
    owner.post(f"/api/items/{item}/owned", json={"condition": "NM"})
    somebody_else.post(f"/api/items/{item}/owned", json={"condition": "Poor"})

    body = _get(owner, "records").text
    row = body[body.index(f"Both {mark}"):][:400]
    assert "NM" in row
    assert "Poor" not in row, "the other person's copy is on the page"
