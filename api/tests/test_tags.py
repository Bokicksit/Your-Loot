"""Are your words yours, and do they stay in the collection you wrote them in?

A tag is the first thing in this app that is free text attached to a shared
catalogue row, which makes it two risks at once. It can leak — the whole point
of `user_id` on the tag table — and it can rot, because "hip-hop", "Hip Hop"
and "HIP_HOP" are one idea typed three ways and three rows in a filter bar,
each holding a third of the records.

Both failures are quiet. A leaked tag looks like a tag. A split one looks like
a shorter list.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=30)


def _tags(c: httpx.Client, scope: str, **params) -> dict[str, int]:
    r = c.get("/api/tags", params={"scope": scope, **params})
    r.raise_for_status()
    return {t["value"]: t["count"] for t in r.json()["tags"]}


def _own(c: httpx.Client, path: str, title: str, body=None) -> int:
    item = c.post(path, json={**(body or {}), "title": title}).json()["id"]
    c.post(f"/api/items/{item}/owned", json={"condition": "NM"}).raise_for_status()
    return item


def _tag(c: httpx.Client, item: int, scope: str, names) -> list[str]:
    r = c.put(f"/api/tags/item/{item}", json={"scope": scope, "names": names})
    r.raise_for_status()
    return r.json()["tags"]


def test_one_word_typed_three_ways_is_one_tag(owner):
    """The rot case. Reusing beats retyping only if a near-miss finds the
    tag that already exists, and the spelling you used first is the one that
    survives — being corrected by your own typo is worse than the typo."""
    mark = uuid.uuid4().hex[:8]
    first, sloppy = f"Hip-Hop-{mark}", f"hip hop {mark}".replace(" ", "_")
    item = _own(owner, "/api/records", f"Rec {mark}")

    _tag(owner, item, "records", [first])
    got = _tag(owner, item, "records", [sloppy.lower(), first.upper(), sloppy])

    assert got == [first], f"expected the original spelling to win, got {got}"
    assert list(_tags(owner, "records")).count(first) == 1


def test_the_same_word_in_two_collections_stays_two_tags(owner):
    """"To reread" on a book and on a film are different shelves' business.
    Scope is what keeps the records filter bar from offering LEGO's labels."""
    word = f"to reread {uuid.uuid4().hex[:8]}"
    book = _own(owner, "/api/books", f"Book {word}")
    film = _own(owner, "/api/movies", f"Film {word}")
    _tag(owner, book, "books", [word])
    _tag(owner, film, "movies", [word])

    listed = owner.get("/api/books", params={"tag": word, "limit": 100}).json()["items"]
    assert [i["id"] for i in listed] == [book], "a books filter returned something else"
    listed = owner.get("/api/movies", params={"tag": word, "limit": 100}).json()["items"]
    assert [i["id"] for i in listed] == [film], "a movies filter returned something else"


def test_games_and_hardware_share_a_table_but_not_a_vocabulary(owner):
    """Hardware has no module of its own — it is a flag on a game — but it is
    its own tab and its own shelf, so it gets its own words."""
    word = f"want to play {uuid.uuid4().hex[:8]}"
    game = _own(owner, "/api/games", f"Game {word}")
    console = _own(owner, "/api/games", f"Console {word}", {"is_hardware": True})
    _tag(owner, game, "games", [word])
    _tag(owner, console, "hardware", [word])

    for is_hw, expected in ((False, game), (True, console)):
        rows = owner.get(
            "/api/games", params={"tag": word, "is_hardware": is_hw, "limit": 100}
        ).json()["items"]
        assert [i["id"] for i in rows] == [expected], f"is_hardware={is_hw} crossed over"


def test_the_count_on_a_chip_matches_what_clicking_it_returns(owner):
    """A tag you kept on something you no longer own must not be advertised
    as if it were still there. A chip reading "(3)" that filters to nothing is
    worse than a zero, because a zero at least looks like one."""
    word = f"shelved {uuid.uuid4().hex[:8]}"
    kept = _own(owner, "/api/lego", f"Kept {word}", {"set_number": "0001-1"})
    _tag(owner, kept, "lego", [word])

    ghost = owner.post("/api/lego", json={"title": f"Ghost {word}", "set_number": "0002-1"}).json()["id"]
    _tag(owner, ghost, "lego", [word])  # tagged, never owned

    counted = _tags(owner, "lego")[word]
    listed = owner.get("/api/lego", params={"tag": word, "limit": 100}).json()["total"]
    assert counted == listed == 1, f"chip says {counted}, filter returns {listed}"


def test_a_tag_follows_something_you_are_still_hunting(owner):
    """"Want to play" is most useful on a thing you do not have yet, so the
    wanted list carries tags and can be counted with them."""
    word = f"hunting {uuid.uuid4().hex[:8]}"
    item = owner.post("/api/records", json={"title": f"Wish {word}"}).json()["id"]
    owner.post(f"/api/items/{item}/wanted", json={}).raise_for_status()
    _tag(owner, item, "records", [word])

    row = next(i for i in owner.get("/api/wanted").json() if i["item_id"] == item)
    assert word in row["tags"], "a wanted row lost its tags"
    assert _tags(owner, "records", include_wanted=True)[word] == 1
    assert _tags(owner, "records")[word] == 0, "an unowned item counted on the shelf"


@pytest.fixture(scope="module")
def people(owner):
    """The owner, and somebody they invited."""
    me = owner.get("/api/auth/me").json()
    if not me["multi_user"]:
        pytest.skip("needs AUTH_MODE=multi")

    email = f"tagbob-{uuid.uuid4().hex[:8]}@example.com"
    owner.post("/api/auth/users", json={"email": email, "password": "bob-password-2"}).raise_for_status()
    bob = _client()
    bob.post("/api/auth/login", json={"email": email, "password": "bob-password-2"}).raise_for_status()
    yield owner, bob
    bob.close()


def test_your_words_are_not_on_anybody_elses_shelf(people):
    """The leak. Two people, one shared catalogue row, and the labels one of
    them wrote on it must be invisible to the other — including in the
    vocabulary that feeds the filter bar and the autocomplete."""
    alice, bob = people
    mark = uuid.uuid4().hex[:8]
    a_word, b_word = f"alice {mark}", f"bob {mark}"

    shared = alice.post("/api/games", json={"title": f"Shared {mark}"}).json()["id"]
    for who in (alice, bob):
        who.post(f"/api/items/{shared}/owned", json={"condition": "NM"}).raise_for_status()
    _tag(alice, shared, "games", [a_word])
    _tag(bob, shared, "games", [b_word])

    assert a_word in _tags(alice, "games") and b_word not in _tags(alice, "games")
    assert b_word in _tags(bob, "games") and a_word not in _tags(bob, "games")

    # Asked for by name rather than taken off the first page. The list is
    # sorted by title and capped, so "Shared …" drifts off the end as the
    # database fills — the same fragility that made the tenancy suite fail one
    # run in two, and for the same reason.
    for who, mine, theirs in ((alice, a_word, b_word), (bob, b_word, a_word)):
        found = who.get(
            "/api/games", params={"search": f"Shared {mark}", "limit": 200}
        ).json()["items"]
        row = next(i for i in found if i["id"] == shared)
        assert row["tags"] == [mine], f"sees {row['tags']}, should see only {mine!r}"
        assert not who.get("/api/games", params={"tag": theirs, "limit": 100}).json()["items"], \
            "filtering by the other person's tag returned rows"


def test_you_cannot_rename_or_delete_somebody_elses_tag(people):
    """Tags are addressed by id, so the id has to be checked against who is
    asking — otherwise renaming is a way to edit a stranger's collection."""
    alice, bob = people
    mark = uuid.uuid4().hex[:8]
    item = _own(alice, "/api/books", f"Book {mark}")
    _tag(alice, item, "books", [f"alice {mark}"])

    tag_id = next(
        t["id"] for t in alice.get("/api/tags", params={"scope": "books"}).json()["tags"]
        if t["value"] == f"alice {mark}"
    )

    assert bob.patch(f"/api/tags/{tag_id}", json={"name": "stolen"}).status_code == 404
    assert bob.delete(f"/api/tags/{tag_id}").status_code == 404
    # and it is still there, under the name she gave it
    assert f"alice {mark}" in _tags(alice, "books")
