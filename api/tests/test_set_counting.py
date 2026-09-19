"""A set binder counts by its own rule: what is filed in it, or anything owned.

A new set binder is strict — the binder in your hands, like the Pokédex: a
Charizard in the Pokédex is not in the set binder until you put one there.
`whole_collection` turns it into a checklist of the collection, which is
what every set binder was before the choice existed.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid

import pytest

SET_NUMBERS = ["1", "2", "3"]


@pytest.fixture
def small_set(owner):
    """Three cards in the catalogue, gone again afterwards."""
    from sqlalchemy import delete, select

    from app.db import SessionLocal
    from app.models import CardAttrs, CollectionItem, Module

    mark = uuid.uuid4().hex[:6]
    code = f"cnt{mark}"
    db = SessionLocal()
    try:
        for n in SET_NUMBERS:
            item = CollectionItem(
                module=Module.cards.value, title=f"Count {code} {n}", source="manual"
            )
            item.card_attrs = CardAttrs(
                set_code=code, set_name=f"Count Set {mark}", card_number=n,
                set_total=len(SET_NUMBERS), language="en",
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


def _cards(owner, code):
    items = owner.get(
        "/api/cards", params={"set_code": code, "collection": False, "limit": 50}
    ).json()["items"]
    return {(i["attrs"]["card_number"] or ""): i for i in items}


def _own(owner, item_id):
    st = owner.post(f"/api/items/{item_id}/owned", json={"condition": "NM"}).json()
    return st["owned"][-1]["id"]


def _shelf_row(owner, binder_id):
    return next(b for b in owner.get("/api/binders").json()["binders"] if b["id"] == binder_id)


def test_a_new_set_binder_is_strict_by_default(owner, small_set):
    cards = _cards(owner, small_set)
    r = owner.post("/api/binders", json={"name": "Strict", "kind": "set", "set_code": small_set})
    r.raise_for_status()
    binder = r.json()["id"]
    try:
        assert r.json()["whole_collection"] is False

        # owning the card is not enough
        copy = _own(owner, cards["1"]["id"])
        page = owner.get(f"/api/binders/{binder}").json()
        assert page["binder"]["filled"] == 0
        assert next(e for e in page["entries"] if e["key"] == "1")["state"] == "missing"
        assert _shelf_row(owner, binder)["filled"] == 0, "the shelf must agree with the page"

        # filing it is
        owner.put(f"/api/binders/{binder}/slots/1", json={"owned_id": copy}).raise_for_status()
        page = owner.get(f"/api/binders/{binder}").json()
        assert page["binder"]["filled"] == 1
        slot = next(e for e in page["entries"] if e["key"] == "1")
        assert slot["state"] == "have" and slot["card"]["owned_id"] == copy
        assert _shelf_row(owner, binder)["filled"] == 1

        # and taking it out empties the slot again, the copy still owned
        owner.delete(f"/api/binders/{binder}/cards/{copy}").raise_for_status()
        page = owner.get(f"/api/binders/{binder}").json()
        assert page["binder"]["filled"] == 0
        assert _cards(owner, small_set)["1"]["owned"], "the copy is still owned"
        # (a strict binder reads its cards with collection=False; the copies
        # ride along on the catalogue row either way)
    finally:
        owner.delete(f"/api/binders/{binder}")


def test_whole_collection_counts_everything_you_own(owner, small_set):
    cards = _cards(owner, small_set)
    _own(owner, cards["2"]["id"])
    r = owner.post(
        "/api/binders",
        json={"name": "Checklist", "kind": "set", "set_code": small_set, "whole_collection": True},
    )
    r.raise_for_status()
    binder = r.json()["id"]
    try:
        assert r.json()["whole_collection"] is True
        page = owner.get(f"/api/binders/{binder}").json()
        assert page["binder"]["filled"] == 1, "owning the card fills its slot on a checklist"

        # the rule can be flipped afterwards, and the count follows it
        owner.patch(f"/api/binders/{binder}", json={"whole_collection": False}).raise_for_status()
        page = owner.get(f"/api/binders/{binder}").json()
        assert page["binder"]["whole_collection"] is False
        assert page["binder"]["filled"] == 0
        assert _shelf_row(owner, binder)["filled"] == 0
        owner.patch(f"/api/binders/{binder}", json={"whole_collection": True}).raise_for_status()
        assert owner.get(f"/api/binders/{binder}").json()["binder"]["filled"] == 1
    finally:
        owner.delete(f"/api/binders/{binder}")


def test_only_a_set_binder_has_a_counting_rule(owner):
    b = owner.post("/api/binders", json={"name": "Mine", "kind": "custom"}).json()["id"]
    try:
        r = owner.patch(f"/api/binders/{b}", json={"whole_collection": True})
        assert r.status_code == 409
    finally:
        owner.delete(f"/api/binders/{b}")


def test_copies_filed_into_a_set_binder_land_in_their_own_slots(owner, small_set):
    cards = _cards(owner, small_set)
    one, three = _own(owner, cards["1"]["id"]), _own(owner, cards["3"]["id"])
    binder = owner.post(
        "/api/binders", json={"name": "Filing", "kind": "set", "set_code": small_set}
    ).json()["id"]
    try:
        # the way the card list files: a batch, no slot named
        r = owner.post(f"/api/binders/{binder}/cards", json={"owned_ids": [three, one]})
        assert r.status_code == 200, r.text
        by_key = {e["key"]: e for e in r.json()["entries"]}
        assert by_key["1"]["card"]["owned_id"] == one
        assert by_key["3"]["card"]["owned_id"] == three
        assert by_key["2"]["state"] == "missing"
        assert r.json()["binder"]["filled"] == 2

        # filing the same copy again is a no-op, not a second slot
        r = owner.post(f"/api/binders/{binder}/cards", json={"owned_ids": [one]})
        assert r.status_code == 200 and r.json()["binder"]["filled"] == 2

        # the copy says where it is
        mine = next(o for o in _cards(owner, small_set)["1"]["owned"] if o["id"] == one)
        assert binder in mine["binder_ids"] and mine["in_custom"]
    finally:
        owner.delete(f"/api/binders/{binder}")


def test_a_card_from_another_set_is_refused_by_name(owner, small_set):
    cards = _cards(owner, small_set)
    inside = _own(owner, cards["2"]["id"])
    stranger_item = owner.post(
        "/api/cards", json={"title": "Stranger From Elsewhere", "card_number": "9"}
    ).json()["id"]
    stranger = _own(owner, stranger_item)
    binder = owner.post(
        "/api/binders", json={"name": "Picky", "kind": "set", "set_code": small_set}
    ).json()["id"]
    try:
        r = owner.post(f"/api/binders/{binder}/cards", json={"owned_ids": [inside, stranger]})
        assert r.status_code == 409, r.text
        assert "Stranger From Elsewhere" in r.json()["detail"]
        # refused whole: the one that did belong was not quietly filed either
        assert owner.get(f"/api/binders/{binder}").json()["binder"]["filled"] == 0
    finally:
        owner.delete(f"/api/binders/{binder}")
        owner.delete(f"/api/cards/{stranger_item}")
