"""Filing cards into binders, now that there can be more than one.

The Pokédex used to be a boolean on the copy and a flag table beside it. This
suite is mostly about the two things that boolean could never say, and one
thing it said by accident.

Could never say: which binder. A card belongs in the Pokédex *and* in the set
binder *and* in the binder of nothing but Charizards, and if filing it in one
takes it out of another the feature is pointless — on the install this was
written against, 881 of 943 copies were already in the Pokédex.

Said by accident: that a slot exists only while something is in it. It does
not. "I am happy with this one" is a fact about the slot, and pulling the card
out to trade it must not erase it. Two bugs during the build erased it anyway
— an orphan cascade, and a foreign key set to CASCADE where it wanted SET
NULL — which is why three tests here do nothing but take a card out and look
at what is left behind.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def _card(c: httpx.Client, title: str, dex: int) -> tuple[int, int]:
    """A card and a copy of it, returned as (item_id, owned_id)."""
    item = c.post(
        "/api/cards",
        json={"title": title, "card_number": "1", "national_dex_no": dex},
    ).json()["id"]
    owned = c.post(f"/api/items/{item}/owned", json={"condition": "NM"}).json()
    return item, owned["owned"][-1]["id"]


def _dex(c: httpx.Client) -> dict[int, dict]:
    entries = c.get("/api/cards/pokedex").json()["entries"]
    return {e["dex_no"]: e for e in entries}


def _file(c: httpx.Client, item: int, owned: int, on: bool = True):
    r = c.patch(f"/api/items/{item}/owned/{owned}", json={"in_binder": on})
    r.raise_for_status()
    return r.json()


@pytest.fixture
def charizard(owner):
    """A card on a dex number nothing else on this install uses."""
    mark = uuid.uuid4().hex[:6]
    # 1025 is the last real slot; the tests that need a free one use it and
    # clean up after themselves
    item, owned = _card(owner, f"Test Card {mark}", 1025)
    yield item, owned
    owner.delete(f"/api/cards/{item}")


def test_filing_a_card_puts_it_in_the_slot(owner, charizard):
    item, owned = charizard
    _file(owner, item, owned)
    slot = _dex(owner)[1025]
    assert slot["card"], "the slot is still empty"
    assert slot["card"]["owned_id"] == owned


def test_the_reply_describes_the_binder_as_it_now_is(owner, charizard):
    """The response is built after the write, so it must reflect it.

    It did not, for a while: `in_binder` is derived from the copy's slots and
    the session does not expire on commit, so the reply described the binder
    as it had been a moment earlier. Filing a card and being told it is not
    filed is the kind of bug you work around for months.
    """
    item, owned = charizard
    said = _file(owner, item, owned)
    assert next(o for o in said["owned"] if o["id"] == owned)["in_binder"] is True

    said = _file(owner, item, owned, on=False)
    assert next(o for o in said["owned"] if o["id"] == owned)["in_binder"] is False


def test_taking_a_card_out_keeps_the_keeper_flag(owner, charizard):
    """The flag is about the slot, not the card that was in it."""
    item, owned = charizard
    _file(owner, item, owned)
    owner.put("/api/cards/pokedex/1025/happy", json={"happy": True}).raise_for_status()
    assert _dex(owner)[1025]["final"] is True

    _file(owner, item, owned, on=False)
    after = _dex(owner)[1025]
    assert after["card"] is None, "the card should have left the slot"
    assert after["final"] is True, "the keeper flag left with it"

    # and it is still there when the card comes back
    _file(owner, item, owned)
    assert _dex(owner)[1025]["final"] is True


def test_deleting_the_copy_empties_the_slot_but_keeps_the_flag(owner):
    """Selling a card is not the same as forgetting you wanted one there."""
    mark = uuid.uuid4().hex[:6]
    item, owned = _card(owner, f"Test Sold {mark}", 1024)
    try:
        _file(owner, item, owned)
        owner.put("/api/cards/pokedex/1024/happy", json={"happy": True})
        owner.delete(f"/api/items/{item}/owned/{owned}").raise_for_status()

        after = _dex(owner)[1024]
        assert after["card"] is None
        assert after["final"] is True
    finally:
        owner.delete(f"/api/cards/{item}")


def test_one_card_per_slot_and_the_last_one_wins(owner):
    """Two copies of the same species cannot both sit in one slot — putting
    the second one in takes the first back out, the way it works in the
    physical binder."""
    mark = uuid.uuid4().hex[:6]
    first_item, first = _card(owner, f"Test First {mark}", 1023)
    second_item, second = _card(owner, f"Test Second {mark}", 1023)
    try:
        _file(owner, first_item, first)
        assert _dex(owner)[1023]["card"]["owned_id"] == first

        _file(owner, second_item, second)
        slot = _dex(owner)[1023]
        assert slot["card"]["owned_id"] == second, "the swap did not happen"

        # the displaced copy is still owned — it went back in the box
        rows = owner.get(f"/api/cards?search=Test First {mark}&include_binder=true").json()
        assert rows["total"] == 1
        assert rows["items"][0]["owned"][0]["in_binder"] is False
    finally:
        owner.delete(f"/api/cards/{first_item}")
        owner.delete(f"/api/cards/{second_item}")


def test_a_filed_card_drops_out_of_the_card_list(owner, charizard):
    """What the list is for: the cards that are *not* on display. Any binder
    counts — a card in a set binder is no less on display than one in the
    Pokédex."""
    item, owned = charizard
    listed = lambda **kw: owner.get("/api/cards", params={"limit": 300, **kw}).json()

    _file(owner, item, owned)
    ids = {i["id"] for i in listed()["items"]}
    assert item not in ids, "a filed card is still in the plain list"
    assert item in {i["id"] for i in listed(include_binder=True)["items"]}

    _file(owner, item, owned, on=False)
    assert item in {i["id"] for i in listed()["items"]}


def test_the_pokedex_is_not_shared(owner):
    """Binders are per person, like everything else here."""
    me = owner.get("/api/auth/me").json()
    if not me.get("multi_user"):
        pytest.skip("single-user install: there is nobody else")

    mark = uuid.uuid4().hex[:6]
    email = f"binder-other-{mark}@example.com"
    owner.post(
        "/api/auth/users", json={"email": email, "password": "other-password-2"}
    ).raise_for_status()
    with httpx.Client(base_url=BASE, timeout=30) as other:
        other.post(
            "/api/auth/login", json={"email": email, "password": "other-password-2"}
        ).raise_for_status()
        item, owned = _card(other, f"Test Theirs {mark}", 1022)
        try:
            _file(other, item, owned)
            assert _dex(other)[1022]["card"] is not None
            assert _dex(owner)[1022]["card"] is None, "their card is in my binder"
        finally:
            other.delete(f"/api/cards/{item}")
