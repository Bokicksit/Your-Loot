"""Your collection, out of one install and into another.

The feature this replaces was a whole-server restore: one button that
deleted every account's rows and reloaded them from a file. This is the
version that cannot do that. Three properties are the whole point.

**It only ever touches the person asking.** Somebody else's collection is
not affected by any request anybody can make here — not by an argument, not
by an admin flag, not by a file that claims otherwise.

**It is the promise that you can leave.** Everybody has it, on every plan,
including the day a plan lapses.

**Hand-typed entries stay with the person who typed them.** They have no
identity anything else would recognise, so an import has to invent a
catalogue row — and a server full of other people should not have one
person's "Dad's old NES" in its search results.

    docker compose -f compose.test.yaml run --rm tests
"""

import io
import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
OPEN = os.environ.get("LOOT_OPEN_URL")


def _zip(c: httpx.Client) -> bytes:
    r = c.get("/api/backup/mine")
    r.raise_for_status()
    assert r.headers["content-type"].startswith("application/zip")
    return r.content


def _restore(c: httpx.Client, blob: bytes, confirm: str = "RESTORE"):
    return c.post(
        "/api/backup/mine",
        files={"file": ("collection.zip", io.BytesIO(blob), "application/zip")},
        data={"confirm": confirm},
    )


def _games(c: httpx.Client, tag: str) -> set[str]:
    found = c.get("/api/games", params={"search": tag, "limit": 200}).json()["items"]
    return {i["title"] for i in found}


def test_a_collection_comes_back_after_it_is_thrown_away(owner):
    """The round trip, on one install: take a copy, lose the lot, put it back."""
    tag = uuid.uuid4().hex[:8]
    title = f"Round trip {tag}"
    item = owner.post("/api/games", json={"title": title}).json()
    owner.post(
        f"/api/items/{item['id']}/owned",
        json={"condition": "LP", "completeness": "CIB", "notes": f"note-{tag}"},
    ).raise_for_status()

    blob = _zip(owner)
    owner.delete(f"/api/games/{item['id']}").raise_for_status()
    assert title not in _games(owner, tag), "the divergence did not take"

    r = _restore(owner, blob)
    r.raise_for_status()

    back = owner.get("/api/games", params={"search": tag, "limit": 200}).json()["items"]
    row = next(i for i in back if i["title"] == title)
    copy = row["owned"][0]
    assert copy["condition"] == "LP", "the condition did not come back"
    assert copy["completeness"] == "CIB"
    assert copy["notes"] == f"note-{tag}", "the note did not come back"


def test_it_will_not_move_without_being_told_to_in_writing(owner):
    """A restore clears what is there first, so it asks for the word rather
    than for a click somebody has learned to dismiss."""
    blob = _zip(owner)
    for wrong in ("", "yes", "restore my collection", "DELETE"):
        r = _restore(owner, blob, confirm=wrong)
        assert r.status_code == 400, f"{wrong!r} was accepted as confirmation"
        assert "RESTORE" in r.json()["detail"]


def test_a_whole_server_backup_is_refused_with_the_reason(owner):
    """The two files look alike and are not. Loading the wrong one used to be
    how you replaced everybody's collection with your own."""
    whole = owner.get("/api/backup").content
    r = _restore(owner, whole)
    assert r.status_code == 400
    assert "whole server" in r.json()["detail"], "refused without saying which file"


@pytest.mark.skipif(not OPEN, reason="needs a second account")
def test_one_person_restoring_cannot_reach_another(owner):
    """The property the old feature could not have: two accounts, one
    restores, and the other one still has everything."""
    mark = uuid.uuid4().hex[:8]
    email = f"bystander-{mark}@example.com"
    with httpx.Client(base_url=OPEN, timeout=60) as them:
        them.post(
            "/api/auth/signup",
            json={"email": email, "password": "a-long-enough-password",
                  "accept_terms": True, "screen_name": f"by{mark}"},
        ).raise_for_status()
        theirs = them.post("/api/games", json={"title": f"Theirs {mark}"}).json()
        them.post(
            f"/api/items/{theirs['id']}/owned", json={"condition": "NM"}
        ).raise_for_status()

        with httpx.Client(base_url=OPEN, timeout=60) as me:
            me.post(
                "/api/auth/signup",
                json={"email": f"restorer-{mark}@example.com",
                      "password": "a-long-enough-password",
                      "accept_terms": True, "screen_name": f"rs{mark}"},
            ).raise_for_status()
            mine = me.post("/api/games", json={"title": f"Mine {mark}"}).json()
            me.post(
                f"/api/items/{mine['id']}/owned", json={"condition": "NM"}
            ).raise_for_status()
            blob = _zip(me)
            _restore(me, blob).raise_for_status()

        still = _games(them, mark)
        assert f"Theirs {mark}" in still, "somebody else's restore took their copy"


@pytest.mark.skipif(not OPEN, reason="needs a second account")
def test_a_hand_typed_entry_arrives_belonging_to_the_person_who_typed_it(owner):
    """It has no id anything else would recognise, so the import has to make
    a catalogue row for it — and that row is theirs, not everybody's."""
    mark = uuid.uuid4().hex[:8]
    typed = f"Dads old console {mark}"

    with httpx.Client(base_url=OPEN, timeout=60) as me:
        me.post(
            "/api/auth/signup",
            json={"email": f"typer-{mark}@example.com",
                  "password": "a-long-enough-password",
                  "accept_terms": True, "screen_name": f"tp{mark}"},
        ).raise_for_status()
        item = me.post("/api/games", json={"title": typed}).json()
        me.post(f"/api/items/{item['id']}/owned", json={"condition": "NM"}).raise_for_status()
        blob = _zip(me)
        _restore(me, blob).raise_for_status()
        assert typed in _games(me, mark), "their own entry did not come back"

    with httpx.Client(base_url=OPEN, timeout=60) as nosy:
        nosy.post(
            "/api/auth/signup",
            json={"email": f"nosy-{mark}@example.com",
                  "password": "a-long-enough-password",
                  "accept_terms": True, "screen_name": f"ny{mark}"},
        ).raise_for_status()
        found = nosy.get(
            "/api/games", params={"search": mark, "limit": 200, "include_wanted_only": True}
        ).json()["items"]
        assert not any(i["title"] == typed for i in found), (
            "an imported hand-typed entry turned up in somebody else's catalogue"
        )


def test_leaving_is_never_behind_the_paywall(owner):
    """Whatever the plan says, the file is there. A collection you cannot get
    out of is a hostage."""
    assert owner.get("/api/backup/mine").status_code == 200


def test_restoring_twice_leaves_one_of_everything(owner):
    """Found by rehearsing this on a real collection, which is the only way
    it would ever have been found.

    A hand-typed item has no id to match on, so the import has to decide
    whether the row in front of it is the same thing. Getting that wrong
    doesn't lose anything — it quietly grows the catalogue by every
    unidentifiable item, every time somebody restores. Restoring onto the
    install a backup came from is the ordinary case, and it should be a
    no-op.
    """
    tag = uuid.uuid4().hex[:8]
    typed = f"Hand typed {tag}"
    item = owner.post("/api/games", json={"title": typed}).json()
    owner.post(
        f"/api/items/{item['id']}/owned", json={"condition": "NM"}
    ).raise_for_status()

    blob = _zip(owner)
    _restore(owner, blob).raise_for_status()
    _restore(owner, blob).raise_for_status()

    found = owner.get(
        "/api/games", params={"search": tag, "limit": 200}
    ).json()["items"]
    assert len(found) == 1, f"restoring twice left {len(found)} of it"
    assert len(found[0]["owned"]) == 1, "and two copies of the one it kept"
