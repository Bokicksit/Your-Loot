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


# --- the other two kinds ---------------------------------------------------
#
# A dex slot is filled by choosing; a set slot is filled by owning. That
# difference is the one thing most likely to be quietly broken by a later
# change, so most of what follows is about it.


# The test stack seeds no catalogue — 20,000 cards is a slow start and no
# other test wants them — so a set binder has no set to be about. These make
# a small one directly in the database, which also lets the ordering test use
# numbers chosen to break a naive sort rather than whatever a real set
# happens to contain.
SET_NUMBERS = ["1", "2", "9", "10", "11", "101", "5a", "TG1", "TG10"]
IN_PRINTED_ORDER = ["1", "2", "5a", "9", "10", "11", "101", "TG1", "TG10"]


@pytest.fixture
def a_set(owner):
    """A set of nine cards in the catalogue, gone again afterwards."""
    from sqlalchemy import delete, select

    from app.db import SessionLocal
    from app.models import CardAttrs, CollectionItem, Module

    mark = uuid.uuid4().hex[:6]
    code = f"tst{mark}"
    db = SessionLocal()
    try:
        for n in SET_NUMBERS:
            item = CollectionItem(
                module=Module.cards.value, title=f"Test {code} {n}", source="manual"
            )
            item.card_attrs = CardAttrs(
                set_code=code, set_name=f"Test Set {mark}", card_number=n,
                set_total=len(SET_NUMBERS),
            )
            db.add(item)
        db.commit()
        yield code
    finally:
        ids = [
            i for (i,) in db.execute(
                select(CollectionItem.id)
                .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
                .where(CardAttrs.set_code == code)
            ).all()
        ]
        if ids:
            db.execute(delete(CollectionItem).where(CollectionItem.id.in_(ids)))
            db.commit()
        db.close()


@pytest.fixture
def a_set_binder(owner, a_set):
    r = owner.post(
        "/api/binders", json={"name": f"Set {a_set}", "kind": "set", "set_code": a_set}
    )
    r.raise_for_status()
    binder = r.json()["id"]
    yield binder, a_set, len(SET_NUMBERS)
    owner.delete(f"/api/binders/{binder}")


def test_a_set_binder_is_filled_by_owning_not_by_filing(owner, a_set_binder):
    """Nobody is going to hand-file two hundred cards to find out which ones
    are missing. Owning the card fills its slot."""
    binder, code, count = a_set_binder
    before = owner.get(f"/api/binders/{binder}").json()
    assert before["binder"]["filled"] == 0, "a fresh set binder should be empty"

    gap = next(e for e in before["entries"] if e["state"] == "missing")
    card = owner.get(
        "/api/cards", params={"set_code": code, "collection": False, "limit": 300}
    ).json()
    target = next(i for i in card["items"] if (i["attrs"]["card_number"] or "") == gap["key"])
    # note: no filing step at all — owning it is the whole action
    owner.post(f"/api/items/{target['id']}/owned", json={"condition": "NM"}).raise_for_status()

    after = owner.get(f"/api/binders/{binder}").json()
    assert after["binder"]["filled"] == before["binder"]["filled"] + 1
    filled = next(e for e in after["entries"] if e["key"] == gap["key"])
    assert filled["state"] != "missing", "owning the card did not fill its slot"


def test_a_set_binder_holds_the_whole_set_in_printed_order(owner, a_set_binder):
    """Every card, secret rares included, and 10 comes after 9 rather than
    after 1 — the numbers are text and sort like text unless told otherwise."""
    binder, code, count = a_set_binder
    entries = owner.get(f"/api/binders/{binder}").json()["entries"]
    assert len(entries) == count
    # 10 after 9 rather than after 1, 5a beside 5, and the TG subset at the
    # end where it is printed
    assert [e["key"] for e in entries] == IN_PRINTED_ORDER


def test_one_binder_per_set(owner, a_set_binder):
    binder, code, _ = a_set_binder
    again = owner.post(
        "/api/binders", json={"name": "again", "kind": "set", "set_code": code}
    )
    assert again.status_code == 409
    assert code in again.json()["detail"] or "already" in again.json()["detail"]


def test_a_set_binder_needs_a_set_we_know(owner):
    r = owner.post(
        "/api/binders", json={"name": "x", "kind": "set", "set_code": "no-such-set"}
    )
    assert r.status_code == 404


def test_a_custom_binder_keeps_the_order_you_put_things_in(owner):
    mark = uuid.uuid4().hex[:6]
    items = [_card(owner, f"Test Custom {mark} {n}", 1000 + n) for n in range(3)]
    r = owner.post("/api/binders", json={"name": f"Custom {mark}", "kind": "custom"})
    binder = r.json()["id"]
    try:
        added = owner.post(
            f"/api/binders/{binder}/cards", json={"owned_ids": [o for _, o in items]}
        ).json()
        assert [e["label"] for e in added["entries"]] == ["1", "2", "3"]
        first_order = [e["name"] for e in added["entries"]]

        slot_ids = [int(e["key"]) for e in added["entries"]]
        flipped = owner.put(
            f"/api/binders/{binder}/order", json={"slot_ids": list(reversed(slot_ids))}
        ).json()
        assert [e["name"] for e in flipped["entries"]] == list(reversed(first_order))

        owner.delete(f"/api/binders/{binder}/slots/{slot_ids[0]}").raise_for_status()
        left = owner.get(f"/api/binders/{binder}").json()
        assert len(left["entries"]) == 2
    finally:
        owner.delete(f"/api/binders/{binder}")
        for item, _ in items:
            owner.delete(f"/api/cards/{item}")


def test_a_card_can_be_in_two_binders_at_once(owner):
    """The whole reason the slot table exists. If filing a card in one binder
    took it out of another, nobody could build a second binder without
    dismantling the Pokédex."""
    mark = uuid.uuid4().hex[:6]
    item, owned = _card(owner, f"Test Both {mark}", 1021)
    r = owner.post("/api/binders", json={"name": f"Both {mark}", "kind": "custom"})
    binder = r.json()["id"]
    try:
        _file(owner, item, owned)                     # into the Pokédex
        owner.post(f"/api/binders/{binder}/cards", json={"owned_ids": [owned]})

        assert _dex(owner)[1021]["card"]["owned_id"] == owned, "left the Pokédex"
        custom = owner.get(f"/api/binders/{binder}").json()
        assert [e["card"]["owned_id"] for e in custom["entries"]] == [owned]
    finally:
        owner.delete(f"/api/binders/{binder}")
        owner.delete(f"/api/cards/{item}")


def test_the_pokedex_cannot_be_deleted(owner):
    """Emptying it is a choice; losing it is not one worth offering."""
    shelf = owner.get("/api/binders").json()["binders"]
    dex = next((b for b in shelf if b["kind"] == "dex"), None)
    if dex is None:
        pytest.skip("nothing filed yet, so there is no Pokédex row")
    assert owner.delete(f"/api/binders/{dex['id']}").status_code == 409


def test_binders_are_not_shared(owner):
    me = owner.get("/api/auth/me").json()
    if not me.get("multi_user"):
        pytest.skip("single-user install: there is nobody else")
    mark = uuid.uuid4().hex[:6]
    email = f"binder-peek-{mark}@example.com"
    owner.post("/api/auth/users", json={"email": email, "password": "other-password-2"})
    r = owner.post("/api/binders", json={"name": f"Mine {mark}", "kind": "custom"})
    binder = r.json()["id"]
    try:
        with httpx.Client(base_url=BASE, timeout=30) as other:
            other.post("/api/auth/login", json={"email": email, "password": "other-password-2"})
            assert other.get(f"/api/binders/{binder}").status_code == 404
            assert other.delete(f"/api/binders/{binder}").status_code == 404
            assert not other.get("/api/binders").json()["binders"]
    finally:
        owner.delete(f"/api/binders/{binder}")
