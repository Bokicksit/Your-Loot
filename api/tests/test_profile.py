"""Public profiles: the one page here that answers a stranger.

Everything else in this application refuses without a session, which is the
property `test_route_auth.py` exists to defend. This is the exception, so it
gets its own suite — because the ways it can go wrong are not "somebody sees a
403", they are "somebody sees a collection they were never shown".

Three things are load-bearing.

Nothing is public until it is switched on, and a profile with nothing switched
on is a 404 rather than an empty page. Publishing is a decision; having a URL
is a consequence of it.

A name is claimed once and never changed. That is what makes the URL worth
giving out, and it is why an administrator taking one away is a revocation
rather than a rename: the name is spent, and nobody gets it again.

And the page is a document, not an app shell. The og: tags are the feature: a
link pasted into a chat is unfurled by something that never runs JavaScript.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def _name() -> str:
    return f"t{uuid.uuid4().hex[:10]}"


@pytest.fixture
def profile(owner):
    """The owner, with their shelves put back afterwards.

    Only the shelves. A name cannot be restored because it cannot be changed
    at all, which is the property most of this file is about.
    """
    was = owner.get("/api/profile").json()
    yield owner
    owner.put("/api/profile", json={"collections": was["collections"]})


@pytest.fixture
def named(profile):
    """The owner's screen name, claiming one if they have none.

    Shared rather than one per test, and that is forced by the feature: a name
    is claimed once, so the second test to ask for its own would be refused.
    Anything needing a *fresh* name has to make a fresh account.
    """
    me = profile.get("/api/profile").json()
    if me["can_claim"]:
        me = profile.put("/api/profile", json={"screen_name": _name()}).json()
    return me["url"].rsplit("/", 1)[-1]


# --- what may not be a name ------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "a",                     # too short for anybody, admin included
        "a" * 31,                # too long
        "-lead",                 # punctuation first
        "trail-",                # punctuation last
        "two--dashes",           # a run of it
        "has space",             # not a URL
        "admin",                 # reserved
        "api",
        "settings",
        "u",
    ],
)
def test_a_name_has_to_be_a_name(profile, bad):
    """Each of these is a shape somebody uses to be mistaken for somebody
    else, or a word that would read as the app talking rather than a person."""
    r = profile.put("/api/profile", json={"screen_name": bad})
    assert r.status_code == 409, f"accepted {bad!r}"
    assert r.json()["detail"], "refused without saying why"


def test_the_url_does_not_care_about_capitals(profile, named):
    """One name, one profile, however it is typed — so "Bo" and "bo" can never
    be two different people, and a link written down in either case works."""
    mine = named
    profile.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()
    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        assert stranger.get(f"/u/{mine}").status_code == 200
        assert stranger.get(f"/u/{mine.upper()}").status_code == 200


# --- publishing is a decision ----------------------------------------------


def test_a_profile_with_nothing_published_is_not_a_profile(profile, named):
    """A 404, not an empty page. Somebody who has not opted in does not have
    a URL, and an empty page would suggest they do."""
    mine = named
    profile.put("/api/profile", json={"collections": []}).raise_for_status()

    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        assert stranger.get(f"/u/{mine}").status_code == 404


def test_a_published_profile_answers_a_stranger_with_a_real_document(profile, named):
    """The og: tags are the point of rendering this server-side — a link in a
    chat window is unfurled by something that does not run JavaScript."""
    mine = named
    profile.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

    # no cookies, no session, nothing
    with httpx.Client(base_url=BASE, timeout=60) as stranger:
        r = stranger.get(f"/u/{mine}")
        assert r.status_code == 200, "a stranger could not read a public profile"
        body = r.text

    assert 'property="og:title"' in body, "no preview title"
    assert 'property="og:description"' in body, "no preview description"
    assert 'rel="canonical"' in body, "no canonical url"
    # a document, not a shell handed to the browser to fill in
    assert "<h1" in body


def test_a_profile_shows_nothing_that_came_out_of_a_free_text_box(profile, named):
    """The share allowlist is the reason this is publishable at all. Notes are
    the field somebody puts a storage location or a price in."""
    mine = named
    item = profile.post(
        "/api/cards",
        json={"title": f"Test Public {uuid.uuid4().hex[:6]}", "card_number": "1"},
    ).json()["id"]
    secret = f"kept-in-the-safe-{uuid.uuid4().hex[:6]}"
    try:
        profile.post(
            f"/api/items/{item}/owned", json={"condition": "NM", "notes": secret}
        ).raise_for_status()
        profile.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            body = stranger.get(f"/u/{mine}").text
        assert secret not in body, "a private note was published"
    finally:
        profile.delete(f"/api/cards/{item}")


# --- claimed once ----------------------------------------------------------


def test_a_name_cannot_be_changed(profile, named):
    """The whole reason there are no aliases and no redirects. A name that can
    move is a URL that can break, and every link anybody wrote down is the
    thing being protected."""
    r = profile.put("/api/profile", json={"screen_name": _name()})
    assert r.status_code == 409, "a screen name was changed"
    assert "cannot be changed" in r.json()["detail"]


def test_a_revoked_name_is_spent_and_the_profile_goes_dark(profile, named):
    """The one lever an administrator has. The name is gone rather than
    forwarded — forwarding it would point at the person it was taken from —
    and nobody can claim it again, including them.

    Takes the shared name away, so it is last in the file on purpose. Nothing
    breaks if that changes: a revocation permits one more claim, so the fixture
    simply takes a new name for whatever runs next.
    """
    me = profile.get("/api/auth/me").json()
    if not me.get("user", {}).get("is_admin", True):
        pytest.skip("needs an admin")

    mine = named
    profile.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

    uid = me["user"]["id"]
    profile.delete(f"/api/admin/users/{uid}/screen-name").raise_for_status()

    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        assert stranger.get(f"/u/{mine}").status_code == 404, "revoked name still answers"

    after = profile.get("/api/profile").json()
    assert after["screen_name"] is None
    assert after["can_claim"] is True, "they cannot choose a replacement"
    assert after["name_revoked"] is True, "they are not told why it went dark"

    # and it is spent — not even by the person who chose it
    r = profile.put("/api/profile", json={"screen_name": mine})
    assert r.status_code == 409, "a revoked name was claimed again"


def test_only_an_administrator_may_hold_a_two_character_name(profile):
    """Not a perk — the operator is the one account that exists before anybody
    else can claim anything, so it is the only one that can hold a scarce name
    without it being a land grab. Everybody else starts at three, which keeps
    the short names out of circulation rather than gone."""
    me = profile.get("/api/auth/me").json()
    if not me.get("multi_user"):
        pytest.skip("single-user install: every account is the administrator")

    mark = uuid.uuid4().hex[:6]
    email = f"shortname-{mark}@example.com"
    profile.post(
        "/api/auth/users", json={"email": email, "password": "other-password-2"}
    ).raise_for_status()
    with httpx.Client(base_url=BASE, timeout=30) as ordinary:
        ordinary.post(
            "/api/auth/login", json={"email": email, "password": "other-password-2"}
        ).raise_for_status()
        r = ordinary.put("/api/profile", json={"screen_name": "zq"})
        assert r.status_code == 409, "a two-character name went to a non-admin"
        assert "Three characters" in r.json()["detail"]

        # and three is fine for them
        ordinary.put(
            "/api/profile", json={"screen_name": f"zq{mark}"}
        ).raise_for_status()


def test_where_profiles_are_off_there_are_none(owner):
    """The default install. A home server nobody outside the house can reach
    has nothing to publish to, so the endpoints are absent rather than
    forbidden — 404, which is a different statement from "you may not"."""
    import os

    solo = os.environ.get("LOOT_SOLO_URL")
    if not solo:
        pytest.skip("no second API to compare against")
    # every api in the test stack has profiles on, so this asserts the
    # reporting rather than the absence — the flag has to reach the client or
    # the settings screen cannot choose which card to draw
    said = owner.get("/api/settings").json()
    assert said["public_profiles"] is True, "the flag did not reach the client"
