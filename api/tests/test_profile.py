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


def test_a_name_with_nothing_published_is_parked_rather_than_missing(profile, named):
    """A name is taken at sign-up, so an address exists before anything is
    chosen to show. It answers with that person's name and nothing else —
    no counts, no shelf names, no hint of what they keep — so a link given
    out early reads as "not yet" rather than as a mistake.

    The publishing decision is untouched: this page carries none of it.
    """
    mine = named
    profile.put("/api/profile", json={"collections": []}).raise_for_status()

    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        r = stranger.get(f"/u/{mine}")
    assert r.status_code == 200, "a claimed name did not answer at all"
    body = r.text
    assert "Not published yet" in body
    assert 'class="stats"' not in body, "a parked page counted something"
    assert 'class="jump"' not in body, "a parked page listed shelves"
    assert 'class="pub-grid"' not in body, "a parked page showed items"
    for shelf in ("Cards", "Records", "Books", "LEGO"):
        assert f"<h2>{shelf}" not in body, f"a parked page named {shelf}"


def test_a_name_nobody_holds_is_still_missing(profile):
    """The parked page is for a name somebody took. One nobody has is a 404,
    or the address space becomes a way to ask whether a name is free."""
    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        assert stranger.get(f"/u/nobody{uuid.uuid4().hex[:10]}").status_code == 404


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


# --- what goes on the shelf ------------------------------------------------


def test_a_binder_kept_back_is_gone_rather_than_undrawn(profile, named):
    """The switch that would be worth nothing if it only changed the drawing.

    A binder held back must not answer on its own route either — a page that
    does not show it and a route that hands it over on request are not the
    same feature, and the second one is the one that decides.
    """
    mine = named
    me = profile.put("/api/profile", json={"collections": ["cards"]}).json()
    if not me["themed"]:
        pytest.skip("no room on this install")

    made = profile.post(
        "/api/binders", json={"name": "Kept Back", "kind": "custom", "pages": 1}
    )
    if made.status_code == 402:
        pytest.skip("this account is at its binder limit")
    made.raise_for_status()
    binder = made.json()["id"]
    try:
        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            assert "Kept Back" in stranger.get(f"/u/{mine}").text
            assert stranger.get(f"/u/{mine}/binder/{binder}").status_code == 200

        profile.patch(f"/api/binders/{binder}", json={"on_profile": False}).raise_for_status()

        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            assert "Kept Back" not in stranger.get(f"/u/{mine}").text, "still on the shelf"
            assert stranger.get(f"/u/{mine}/binder/{binder}").status_code == 404, (
                "a binder kept back still handed over its pages"
            )
    finally:
        profile.delete(f"/api/binders/{binder}")


def test_hiding_a_binder_does_not_tip_its_cards_into_the_loose_box(profile, named):
    """The trap under the last test. Loose means "in no binder", so a binder
    that is skipped rather than merely undrawn would publish every card in it
    as loose — hiding the shelf by scattering it."""
    mine = named
    me = profile.put("/api/profile", json={"collections": ["cards"]}).json()
    if not me["themed"]:
        pytest.skip("no room on this install")

    mark = uuid.uuid4().hex[:6]
    item = profile.post(
        "/api/cards", json={"title": f"Filed Away {mark}", "card_number": "1"}
    ).json()["id"]
    made = profile.post(
        "/api/binders", json={"name": f"Private {mark}", "kind": "custom", "pages": 1}
    )
    if made.status_code == 402:
        profile.delete(f"/api/cards/{item}")
        pytest.skip("this account is at its binder limit")
    binder = made.json()["id"]
    try:
        # the response is the item's whole status, so the new copy is the
        # one on the end of it
        copies = profile.post(
            f"/api/items/{item}/owned", json={"condition": "NM"}
        ).json()["owned"]
        slot = profile.get(f"/api/binders/{binder}").json()["entries"][0]["key"]
        profile.put(
            f"/api/binders/{binder}/slots/{slot}",
            json={"owned_id": copies[-1]["id"], "item_id": item},
        ).raise_for_status()
        profile.patch(f"/api/binders/{binder}", json={"on_profile": False}).raise_for_status()

        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            body = stranger.get(f"/u/{mine}").text
        assert f"Private {mark}" not in body, "the binder is still shown"
        assert f"Filed Away {mark}" not in body, "a card in a hidden binder came out loose"
    finally:
        profile.delete(f"/api/binders/{binder}")
        profile.delete(f"/api/cards/{item}")


def test_the_loose_box_can_be_left_off_the_shelf(profile, named):
    """Some of a collection is in binders and some is in a box, and they are
    separate decisions — a shelf of binders is a thing somebody may want to
    show without the pile beside it."""
    mine = named
    me = profile.put("/api/profile", json={"collections": ["cards"]}).json()
    if not me["themed"]:
        pytest.skip("no room on this install")
    assert me["loose"] is True, "the box should be shown until it is turned off"

    mark = uuid.uuid4().hex[:6]
    item = profile.post(
        "/api/cards", json={"title": f"Loose One {mark}", "card_number": "2"}
    ).json()["id"]
    try:
        profile.post(f"/api/items/{item}/owned", json={"condition": "NM"}).raise_for_status()

        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            assert f"Loose One {mark}" in stranger.get(f"/u/{mine}").text

        after = profile.put("/api/profile", json={"loose": False}).json()
        assert after["loose"] is False
        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            assert f"Loose One {mark}" not in stranger.get(f"/u/{mine}").text, (
                "the box was turned off and its cards are still on the page"
            )
    finally:
        profile.put("/api/profile", json={"loose": True})
        profile.delete(f"/api/cards/{item}")


@pytest.mark.skipif(not os.environ.get("LOOT_OPEN_URL"), reason="needs a fresh account")
def test_a_card_that_lives_in_a_binder_is_still_part_of_the_collection():
    """Found on a live profile that said "0 things" while holding a card.

    The cards list hides binder-filed cards, because in the app the binder is
    its own page. A profile has no other page to send anybody to, and for most
    people the binders are where the collection actually is — so a shelf that
    left them out reported a Pokedex of nine hundred cards as the handful
    nobody had filed yet, and an account whose one card was filed as nothing
    at all.

    Asked of a brand new account, because the number has to be the whole
    answer: on a shelf that already has things on it, one more is invisible.
    """
    import re

    open_url = os.environ["LOOT_OPEN_URL"]
    mark = uuid.uuid4().hex[:6]
    with httpx.Client(base_url=open_url, timeout=60) as me:
        me.post("/api/auth/signup", json={
            "email": f"binderonly-{mark}@example.com",
            "password": "a-long-enough-password",
            "accept_terms": True, "screen_name": f"bo{mark}",
        }).raise_for_status()

        item = me.post(
            "/api/cards", json={"title": f"Filed Only {mark}", "card_number": "1"}
        ).json()["id"]
        copies = me.post(
            f"/api/items/{item}/owned", json={"condition": "NM"}
        ).json()["owned"]
        made = me.post(
            "/api/binders", json={"name": f"Shelf {mark}", "kind": "custom", "pages": 1}
        )
        if made.status_code == 402:
            pytest.skip("this install caps binders on the free plan")
        binder = made.json()["id"]
        slot = me.get(f"/api/binders/{binder}").json()["entries"][0]["key"]
        me.put(
            f"/api/binders/{binder}/slots/{slot}",
            json={"owned_id": copies[-1]["id"], "item_id": item},
        ).raise_for_status()

        # the card is now in a binder and nowhere else
        loose = me.get("/api/cards", params={"limit": 5}).json()["total"]
        assert loose == 0, "the card was supposed to be filed away"

        me.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

    with httpx.Client(base_url=open_url, timeout=60) as stranger:
        body = stranger.get(f"/u/bo{mark}").text
    said = re.search(r"(\d+) things", body)
    assert said, "the profile did not say how much is on it"
    assert int(said.group(1)) == 1, (
        f"a filed card counted as {said.group(1)} things on the profile"
    )


@pytest.mark.skipif(not os.environ.get("LOOT_OPEN_URL"), reason="needs a fresh account")
def test_an_empty_published_profile_says_so_in_words_that_change():
    """A shelf published before anything is on it. A grid of zero items and a
    jump rail to empty sections present absence as a layout bug; one line —
    drawn at random from a pool on every view, assigned to nobody — says it
    on purpose and keeps the page alive."""
    import re

    open_url = os.environ["LOOT_OPEN_URL"]
    mark = uuid.uuid4().hex[:6]
    with httpx.Client(base_url=open_url, timeout=60) as me:
        me.post("/api/auth/signup", json={
            "email": f"blank-{mark}@example.com",
            "password": "a-long-enough-password",
            "accept_terms": True, "screen_name": f"bl{mark}",
        }).raise_for_status()
        me.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

    lines = set()
    with httpx.Client(base_url=open_url, timeout=60) as stranger:
        for _ in range(25):
            page = stranger.get(f"/u/bl{mark}").text
            body = page.split("</style>", 1)[1]  # the stylesheet mentions the classes too
            m = re.search(r'pub-empty"><p>([^<]+)</p>', body)
            assert m, "an empty profile had no line to say so"
            lines.add(m.group(1))
            assert 'class="pub-grid"' not in body, "an empty grid was drawn anyway"
            assert 'class="jump"' not in body, "a jump rail to nothing"
    assert len(lines) > 1, "the line never changed — that is a motto, not a rotation"


# --- what a Supporter gets -------------------------------------------------


def _looks_like(body: str) -> str:
    if 'class="room2-page"' in body:
        assert ".scene-strip" in body, "a room without the stylesheet to draw it"
        return "room"
    assert 'class="pub"' in body
    assert ".scene-strip" not in body, "a plain page carried 30 KB of furniture"
    return "grid"


def test_the_page_a_stranger_gets_is_the_one_the_owner_was_promised(profile, named):
    """The room is the one thing a tier changes about a public page — and both
    pages publish exactly the same shelves and items, so what changes is how
    they are drawn, never what is shown.

    Asserted against what /api/profile told the owner rather than against a
    hard-coded tier, because the answer differs by install on purpose: where
    nothing is sold there is no tier to be outside of and everybody in the
    house gets the room.
    """
    mine = named
    me = profile.put(
        "/api/profile", json={"collections": ["cards"]}
    ).json()

    with httpx.Client(base_url=BASE, timeout=60) as stranger:
        body = stranger.get(f"/u/{mine}").text
    want = "room" if me["themed"] else "grid"
    assert _looks_like(body) == want, "the owner was promised the other page"


def test_an_ordinary_account_is_told_the_same_thing_a_stranger_sees(profile):
    """The half of it an administrator cannot test on themselves: admins are
    never billed, so this account always gets the room where one is on offer."""
    who = profile.get("/api/auth/me").json()
    if not who.get("multi_user"):
        pytest.skip("single-user install: the only account is the administrator")

    mark = uuid.uuid4().hex[:6]
    email = f"freetier-{mark}@example.com"
    profile.post(
        "/api/auth/users", json={"email": email, "password": "other-password-3"}
    ).raise_for_status()
    with httpx.Client(base_url=BASE, timeout=30) as free:
        free.post(
            "/api/auth/login", json={"email": email, "password": "other-password-3"}
        ).raise_for_status()
        # Something on the shelf. An empty room is not drawn at all — a stage
        # with no furniture on it says something untrue about the person — so
        # an account with nothing would fall back to the grid whatever it was
        # promised, and would not be testing the tier.
        item = free.post(
            "/api/cards", json={"title": f"Free Tier {mark}", "card_number": "1"}
        ).json()["id"]
        free.post(f"/api/items/{item}/owned", json={"condition": "NM"}).raise_for_status()
        told = free.put(
            "/api/profile",
            json={"screen_name": f"ft{mark}", "collections": ["cards"]},
        ).json()

    with httpx.Client(base_url=BASE, timeout=60) as stranger:
        body = stranger.get(f"/u/ft{mark}").text
    assert _looks_like(body) == ("room" if told["themed"] else "grid")


# --- what is inside the furniture ------------------------------------------


def test_a_room_can_be_opened_and_a_binder_is_not_in_the_page(profile, named):
    """The drill: the room says how much, this says what.

    The carousels are in the document, because they are the same items the
    plain page lists and a crawler should still find them. A binder's pockets
    are not — a Pokedex is 1,025 of them, and building that into a page for a
    binder most visitors never open would cost more than the collection it is
    showing.
    """
    mine = named
    me = profile.put("/api/profile", json={"collections": ["cards"]}).json()
    if not me["themed"]:
        pytest.skip("no room on this install, so nothing to drill into")

    with httpx.Client(base_url=BASE, timeout=60) as stranger:
        body = stranger.get(f"/u/{mine}").text
    assert 'id="drill-cards"' in body, "the furniture does not open"
    assert 'class="binder-rail"' in body, "no shelf of binders inside it"
    assert '"slots"' not in body, "a binder's pockets were built into the page"


def test_a_binder_answers_the_same_stranger_the_page_does(profile, named):
    """And answers with the empty slots too. A binder is as much what is
    missing as what is in it, and a list of only the cards somebody owns is
    the grid, which they can already see."""
    mine = named
    me = profile.put("/api/profile", json={"collections": ["cards"]}).json()
    if not me["themed"]:
        pytest.skip("no room on this install")

    # An empty binder of two pages: a shelf that is mostly gaps, which is the
    # half of a binder a grid of owned cards can never show.
    made = profile.post(
        "/api/binders", json={"name": "Public Shelf", "kind": "custom", "pages": 2}
    )
    if made.status_code == 402:
        pytest.skip("this account is at its binder limit")
    made.raise_for_status()
    binder = made.json()["id"]
    try:
        with httpx.Client(base_url=BASE, timeout=60) as stranger:
            r = stranger.get(f"/u/{mine}/binder/{binder}")
            assert r.status_code == 200, "a public binder refused a stranger"
            data = r.json()
        assert data["name"] == "Public Shelf"
        assert data["slots"], "a binder with no pockets"
        assert len(data["slots"]) == data["total"]
        assert any(s[3] == 0 for s in data["slots"]), "the gaps were left out"
        assert data["pages"] >= 1

        # and it is gone the moment the shelf is unpublished
        profile.put("/api/profile", json={"collections": []}).raise_for_status()
        with httpx.Client(base_url=BASE, timeout=30) as stranger:
            assert stranger.get(f"/u/{mine}/binder/{binder}").status_code == 404
    finally:
        profile.delete(f"/api/binders/{binder}")


def test_a_binder_is_only_public_through_its_own_profile(profile, named):
    """The URL names a person and a binder, and the two have to agree. A
    binder belonging to somebody else is a 404 even where the profile in the
    path is perfectly public — otherwise one published profile would be a
    door to every binder on the server."""
    mine = named
    profile.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

    with httpx.Client(base_url=BASE, timeout=30) as stranger:
        # a binder id that cannot belong to anybody
        assert stranger.get(f"/u/{mine}/binder/99999999").status_code == 404
        assert stranger.get(f"/u/{mine}/binder/0").status_code == 404


def test_where_profiles_are_off_there_are_none(owner):
    """The default install, and the answer to "is this only for the hosted
    service".

    It is not a different build — it is the same image with the switch off,
    which is how everything else in this app is decided too. But off has to
    mean gone rather than hidden: no endpoint to claim a name with, no page
    to find, and nothing in the settings answer that would make a client draw
    a profile card for a feature this server does not have.
    """
    said = owner.get("/api/settings").json()
    assert said["public_profiles"] is True, "the flag did not reach the client"

    solo = os.environ.get("LOOT_SOLO_URL")
    if not solo:
        pytest.skip("no install with profiles off to compare against")

    with httpx.Client(base_url=solo, timeout=30) as home:
        assert home.get("/api/settings").json()["public_profiles"] is False
        # absent, not forbidden — a different statement from "you may not"
        assert home.get("/api/profile").status_code == 404
        assert home.put("/api/profile", json={"screen_name": _name()}).status_code == 404
        assert home.get("/u/anybody").status_code == 404
        assert home.get("/u/anybody/binder/1").status_code == 404


def test_signing_up_where_there_are_no_profiles_asks_for_no_name(owner):
    """A name is the address of a public page. Where there are none there is
    no address to choose, and requiring one would be asking somebody to name
    a page that does not exist on their server.

    This is the shape the sign-up form is drawn from, which is why the flag
    is on /api/auth/me as well: the form and the handler have to agree about
    whether the field exists, and they did not — the server required a name
    the form never asked for, and open sign-up answered 422 to everybody.
    """
    solo = os.environ.get("LOOT_SOLO_URL")
    if not solo:
        pytest.skip("no install with profiles off to compare against")
    with httpx.Client(base_url=solo, timeout=30) as home:
        assert home.get("/api/auth/me").json().get("public_profiles") is False


def test_signing_up_where_there_are_profiles_requires_a_name(owner):
    """And the other half, on the install that has them: a name is part of
    making the account, refused in a sentence rather than as a schema error,
    because it is a thing to choose rather than a field to fill in."""
    open_url = os.environ.get("LOOT_OPEN_URL")
    if not open_url:
        pytest.skip("no install with open sign-up to test against")

    with httpx.Client(base_url=open_url, timeout=60) as anyone:
        assert anyone.get("/api/auth/me").json().get("public_profiles") is True

        mark = uuid.uuid4().hex[:8]
        body = {
            "email": f"noname-{mark}@example.com",
            "password": "a-long-enough-password",
            "accept_terms": True,
        }
        r = anyone.post("/api/auth/signup", json=body)
        assert r.status_code == 409, "signed up with no name where names are the point"
        assert r.json()["detail"], "refused without saying why"

        # and the payload the form actually sends goes through
        body["screen_name"] = f"nm{mark}"
        anyone.post("/api/auth/signup", json=body).raise_for_status()


# --- the home server's own page ---------------------------------------------

HOME = os.environ.get("LOOT_HOME_URL")
needs_home = pytest.mark.skipif(
    not HOME, reason="no single-user install with profiles on"
)


@needs_home
def test_a_home_server_shows_its_room_at_a_fixed_address():
    """One person, no accounts, so no name to claim: the page is /loot.

    And because nothing is sold on a home server, there is no tier to be
    outside of — the room is everyone's, which here means the owner's.
    """
    import re

    with httpx.Client(base_url=HOME, timeout=60) as owner:
        # publishing is still the same opt-in — nothing ticked, no page
        owner.put("/api/profile", json={"collections": []}).raise_for_status()
        assert httpx.get(f"{HOME}/loot", timeout=30).status_code == 404, (
            "an unpublished /loot page answered"
        )

        me = owner.get("/api/profile").json()
        assert me["fixed_url"] is True and me["url"] == "/loot"
        assert me["can_claim"] is False, "a home server offered a name to claim"
        r = owner.put("/api/profile", json={"screen_name": "anything"})
        assert r.status_code == 409, "a home server accepted a screen name"

        item = owner.post(
            "/api/cards", json={"title": "Home Card", "card_number": "1"}
        ).json()["id"]
        try:
            owner.post(
                f"/api/items/{item}/owned", json={"condition": "NM"}
            ).raise_for_status()
            owner.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

            page = httpx.get(f"{HOME}/loot", timeout=60)
            assert page.status_code == 200, "a published /loot page refused a stranger"
            body = page.text
            assert 'class="room2-page"' in body, "a home server did not get the room"
            assert 'property="og:title"' in body

            # the page's data lives under its own prefix — that is what lets
            # a tunnel expose exactly one path
            binder_id = re.search(r'data-binder="(\d+)"', body)
            if binder_id:
                assert httpx.get(
                    f"{HOME}/loot/binder/{binder_id.group(1)}", timeout=30
                ).status_code == 200
        finally:
            owner.put("/api/profile", json={"collections": []})
            owner.delete(f"/api/cards/{item}")


@needs_home
def test_the_loot_page_never_points_outside_its_own_surface():
    """The guarantee the tunnel guide rests on. Somebody exposing /loot,
    /images/ and /assets/ has exposed the whole page — every URL in the
    document stays inside that surface or goes to another host entirely, so
    following the guide can never leak a route into the rest of the server."""
    import re

    with httpx.Client(base_url=HOME, timeout=60) as owner:
        item = owner.post(
            "/api/cards", json={"title": "Surface Card", "card_number": "2"}
        ).json()["id"]
        try:
            owner.post(
                f"/api/items/{item}/owned", json={"condition": "NM"}
            ).raise_for_status()
            owner.put("/api/profile", json={"collections": ["cards"]}).raise_for_status()

            body = httpx.get(f"{HOME}/loot", timeout=60).text
            refs = re.findall(r'(?:href|src)="([^"]+)"', body)
            refs += re.findall(r"url\('([^']+)'\)", body)
            allowed = ("/loot", "/images/", "/assets/", "/", "#", "http://", "https://", "data:")
            for ref in refs:
                assert ref.startswith(allowed), f"{ref} points outside the exposed surface"
                # bare "/" is the footer link home; anything longer must be on the list
                if ref.startswith("/") and not ref.startswith(("//", "/loot", "/images/", "/assets/")):
                    assert ref == "/", f"{ref} points outside the exposed surface"
        finally:
            owner.put("/api/profile", json={"collections": []})
            owner.delete(f"/api/cards/{item}")


def test_where_there_are_accounts_there_is_no_loot_page(owner):
    """A URL that means "the owner" on a server full of people would be a
    page about whoever runs it that they never asked for."""
    r = owner.get("/loot")
    assert r.status_code == 404, "/loot answered on a multi-user install"


# --- reserved names --------------------------------------------------------
#
# A name is claimed once, which makes the moment of claiming the only one
# that matters. A reservation lets the operator get ahead of it: hold a name
# for somebody who has no account yet, and point it at their email when they
# finally do.


def _invite(owner, email):
    owner.post(
        "/api/auth/users", json={"email": email, "password": "test-password-9"}
    ).raise_for_status()
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post(
        "/api/auth/login", json={"email": email, "password": "test-password-9"}
    ).raise_for_status()
    return c


def test_a_reserved_name_waits_for_its_person(owner):
    held = _name()
    r = owner.post("/api/admin/reserved-names", json={"name": held})
    assert r.status_code == 201, r.text
    res_id = r.json()["id"]

    stranger = _invite(owner, f"s-{uuid.uuid4().hex[:8]}@example.com")
    kid_email = f"k-{uuid.uuid4().hex[:8]}@example.com"
    kid = _invite(owner, kid_email)
    try:
        # held for nobody yet: everybody bounces
        r = stranger.put("/api/profile", json={"screen_name": held})
        assert r.status_code >= 400, "a stranger claimed a reserved name"

        # assigned to the kid: the stranger still bounces, the kid gets in
        owner.patch(
            f"/api/admin/reserved-names/{res_id}", json={"email": kid_email}
        ).raise_for_status()
        r = stranger.put("/api/profile", json={"screen_name": held})
        assert r.status_code >= 400, "assigning it did not keep a stranger out"
        # and the kid cannot accidentally spend their once-ever claim on a
        # different name while this one waits — that would strand it forever
        r = kid.put("/api/profile", json={"screen_name": _name()})
        assert r.status_code >= 400, "a claim burned while a name was held for them"
        assert "held" in r.json()["detail"].lower(), "refused without saying a name waits"
        r = kid.put("/api/profile", json={"screen_name": held})
        assert r.status_code == 200, r.text
        assert r.json()["url"].endswith("/" + held)

        # spent by the claiming: no longer on the admin's list
        names = {
            row["name"] for row in owner.get("/api/admin/reserved-names").json()
        }
        assert held not in names, "a claimed reservation is still listed"
    finally:
        stranger.close()
        kid.close()


def test_a_released_name_goes_back_in_circulation(owner):
    held = _name()
    res = owner.post("/api/admin/reserved-names", json={"name": held}).json()
    someone = _invite(owner, f"r-{uuid.uuid4().hex[:8]}@example.com")
    try:
        assert someone.put("/api/profile", json={"screen_name": held}).status_code >= 400
        owner.delete(f"/api/admin/reserved-names/{res['id']}").raise_for_status()
        r = someone.put("/api/profile", json={"screen_name": held})
        assert r.status_code == 200, "a released name could not be claimed"
    finally:
        someone.close()


def test_a_reservation_cannot_take_a_held_name(owner, named):
    """Reserving gets ahead of a claim; it never undoes one. The lever for a
    name somebody holds is revocation, which spends it for everybody."""
    r = owner.post("/api/admin/reserved-names", json={"name": named})
    assert r.status_code == 409, "a reservation displaced a held name"


def test_a_reservation_holds_through_signup():
    """The same gate at the door names are usually claimed through.

    On the open-signup install the name is part of making the account, so
    the reservation has to answer there too: a stranger asking for the held
    name is refused in a sentence, the person it waits for is stopped from
    burning their claim on something else, and signing up with the held
    name works and spends the reservation.
    """
    open_url = os.environ.get("LOOT_OPEN_URL")
    if not open_url:
        pytest.skip("no install with open sign-up to test against")

    # the same credentials test_accounts claims the open install's first
    # account with — whichever file gets there first, the other signs in
    creds = {"email": "open-owner@example.com", "password": "the-owner-password-1"}
    admin = httpx.Client(base_url=open_url, timeout=60)
    me = admin.get("/api/auth/me").json()
    if me.get("needs_setup"):
        admin.post("/api/auth/setup", json=creds).raise_for_status()
    elif admin.post("/api/auth/login", json=creds).status_code != 200:
        admin.close()
        pytest.skip("the open install already belongs to somebody")

    try:
        held = _name()
        kid_email = f"kid-{uuid.uuid4().hex[:8]}@example.com"
        admin.post(
            "/api/admin/reserved-names", json={"name": held, "email": kid_email}
        ).raise_for_status()

        password = "a-long-enough-password"
        with httpx.Client(base_url=open_url, timeout=60) as stranger:
            r = stranger.post("/api/auth/signup", json={
                "email": f"x-{uuid.uuid4().hex[:8]}@example.com",
                "password": password,
                "accept_terms": True,
                "screen_name": held,
            })
            assert r.status_code == 409, "a stranger signed up under a held name"
            assert "reserved" in r.json()["detail"].lower()

        with httpx.Client(base_url=open_url, timeout=60) as kid:
            r = kid.post("/api/auth/signup", json={
                "email": kid_email,
                "password": password,
                "accept_terms": True,
                "screen_name": _name(),
            })
            assert r.status_code == 409, "signup burned a claim while a name waited"
            assert "held" in r.json()["detail"].lower()

            r = kid.post("/api/auth/signup", json={
                "email": kid_email,
                "password": password,
                "accept_terms": True,
                "screen_name": held,
            })
            assert r.status_code < 300, r.text

        names = {
            row["name"] for row in admin.get("/api/admin/reserved-names").json()
        }
        assert held not in names, "a signup-claimed reservation is still listed"
    finally:
        admin.close()


def test_reservations_are_the_admins_business(owner):
    other = _invite(owner, f"n-{uuid.uuid4().hex[:8]}@example.com")
    try:
        assert other.get("/api/admin/reserved-names").status_code == 403
        assert (
            other.post(
                "/api/admin/reserved-names", json={"name": _name()}
            ).status_code
            == 403
        )
    finally:
        other.close()
