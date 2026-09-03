"""A binder of your own: pockets you point at, and a card list that says
where each copy is.

Two things that were true of a real binder and not of this one. You can
slide a card into *this* empty sleeve rather than the first empty one; and a
card that is in the Pokédex and in a binder of yours is in both, which the
collection should say rather than picking one.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


@pytest.fixture
def me(owner):
    return owner


def a_card(c, name, dex=None):
    body = {"title": f"{name} {uuid.uuid4().hex[:6]}"}
    if dex is not None:
        body["national_dex_no"] = dex
    item = c.post("/api/cards", json=body).json()
    st = c.post(f"/api/items/{item['id']}/owned", json={"quantity": 1}).json()
    return item["id"], st["owned"][-1]["id"]


def pockets(c, binder_id):
    return c.get(f"/api/binders/{binder_id}").json()["entries"]


def owned_of(c, item_id):
    rows = c.get("/api/cards", params={"collection": True, "include_binder": True, "limit": 300}).json()["items"]
    return next(i for i in rows if i["id"] == item_id)["owned"]


# ---------------------------------------------------------- pointing at a pocket

def test_a_blank_pocket_can_be_filled_by_pointing_at_it(me):
    b = me.post("/api/binders", json={"name": "Pockets", "kind": "custom", "pages": 1}).json()
    ps = pockets(me, b["id"])
    assert len(ps) == 9 and all(p["blank"] for p in ps)   # 3×3, all empty

    item, copy = a_card(me, "Sleeve me")
    target = ps[4]   # the middle one, not the first
    r = me.put(f"/api/binders/{b['id']}/slots/{target['key']}", json={"owned_id": copy})
    assert r.status_code == 200, r.text

    after = pockets(me, b["id"])
    assert after[4]["card"] and after[4]["card"]["id"] == item
    assert all(p["blank"] for i, p in enumerate(after) if i != 4), "only the pocket pointed at filled"

    # and emptied the same way: the pocket stays, blank
    me.put(f"/api/binders/{b['id']}/slots/{target['key']}", json={"owned_id": None}).raise_for_status()
    again = pockets(me, b["id"])
    assert len(again) == 9 and again[4]["blank"]
    me.delete(f"/api/binders/{b['id']}")


def test_one_copy_cannot_sit_in_two_pockets_of_the_same_binder(me):
    b = me.post("/api/binders", json={"name": "Twice", "kind": "custom", "pages": 1}).json()
    ps = pockets(me, b["id"])
    _, copy = a_card(me, "Only one of me")
    me.put(f"/api/binders/{b['id']}/slots/{ps[0]['key']}", json={"owned_id": copy}).raise_for_status()
    r = me.put(f"/api/binders/{b['id']}/slots/{ps[1]['key']}", json={"owned_id": copy})
    assert r.status_code == 409
    assert "already in this binder" in r.json()["detail"]
    me.delete(f"/api/binders/{b['id']}")


def test_a_pocket_that_is_not_in_this_binder_is_not_found(me):
    b1 = me.post("/api/binders", json={"name": "A", "kind": "custom", "pages": 1}).json()
    b2 = me.post("/api/binders", json={"name": "B", "kind": "custom", "pages": 1}).json()
    foreign = pockets(me, b2["id"])[0]["key"]
    _, copy = a_card(me, "Wrong binder")
    assert me.put(f"/api/binders/{b1['id']}/slots/{foreign}", json={"owned_id": copy}).status_code == 404
    assert me.put(f"/api/binders/{b1['id']}/slots/not-a-number", json={"owned_id": copy}).status_code == 404
    for b in (b1, b2):
        me.delete(f"/api/binders/{b['id']}")


# ------------------------------------------------ the card list says where it is

def test_a_copy_reports_the_pokedex_and_a_binder_separately(me):
    b = me.post("/api/binders", json={"name": "Mine", "kind": "custom", "pages": 1}).json()
    item, copy = a_card(me, "Pikachu", dex=25)

    o = owned_of(me, item)[0]
    assert (o["in_binder"], o["in_custom"]) == (False, False)      # loose in a box

    me.post(f"/api/binders/{b['id']}/cards", json={"owned_ids": [copy]}).raise_for_status()
    o = owned_of(me, item)[0]
    assert (o["in_binder"], o["in_custom"]) == (False, True)       # in a binder of mine

    me.patch(f"/api/items/{item}/owned/{copy}", json={"in_binder": True}).raise_for_status()
    o = owned_of(me, item)[0]
    assert (o["in_binder"], o["in_custom"]) == (True, True)        # in both — and it says both

    me.patch(f"/api/items/{item}/owned/{copy}", json={"in_binder": False}).raise_for_status()
    o = owned_of(me, item)[0]
    assert (o["in_binder"], o["in_custom"]) == (False, True)       # leaving the Pokédex leaves the binder alone
    me.delete(f"/api/binders/{b['id']}")


# ------------------------------------------------------- a stack in one pocket

def three_of(c, name):
    """Three copies of one card — the same catalogue row, three owned rows."""
    item = c.post("/api/cards", json={"title": f"{name} {uuid.uuid4().hex[:6]}"}).json()["id"]
    copies = []
    for _ in range(3):
        st = c.post(f"/api/items/{item}/owned", json={"quantity": 1}).json()
        copies.append(st["owned"][-1]["id"])
    return item, copies


def test_the_same_card_stacks_in_one_pocket_up_to_three(me):
    b = me.post("/api/binders", json={"name": "Spares", "kind": "custom", "pages": 1}).json()
    key = pockets(me, b["id"])[0]["key"]
    item, copies = three_of(me, "Dupe")
    for i, cid in enumerate(copies, start=1):
        r = me.put(f"/api/binders/{b['id']}/slots/{key}", json={"owned_id": cid})
        assert r.status_code == 200, r.text
        top = pockets(me, b["id"])[0]
        assert top["card"]["id"] == item and top["count"] == i
        assert len(top["stack"]) == i - 1

    # still nine pockets — a stack is one pocket
    assert len(pockets(me, b["id"])) == 9

    # a fourth is refused, and so is a different card
    _, extra = a_card(me, "Fourth")
    fourth_same = me.post(f"/api/items/{item}/owned", json={"quantity": 1}).json()["owned"][-1]["id"]
    assert me.put(f"/api/binders/{b['id']}/slots/{key}", json={"owned_id": fourth_same}).status_code == 409
    r = me.put(f"/api/binders/{b['id']}/slots/{key}", json={"owned_id": extra})
    assert r.status_code == 409 and "different card" in r.json()["detail"]
    me.delete(f"/api/binders/{b['id']}")


def test_taking_one_out_of_a_stack_keeps_the_pocket_and_its_place(me):
    b = me.post("/api/binders", json={"name": "Stack", "kind": "custom", "pages": 1}).json()
    ps = pockets(me, b["id"])
    key = ps[3]["key"]                     # the fourth pocket
    item, copies = three_of(me, "Trio")
    for cid in copies:
        me.put(f"/api/binders/{b['id']}/slots/{key}", json={"owned_id": cid}).raise_for_status()

    # a spare leaves: pocket unchanged, two remain
    me.delete(f"/api/binders/{b['id']}/cards/{copies[2]}").raise_for_status()
    p = pockets(me, b["id"])[3]
    assert p["key"] == key and p["count"] == 2 and p["card"]["id"] == item

    # the top card leaves: the next one takes the pocket — same key, same place
    me.delete(f"/api/binders/{b['id']}/cards/{copies[0]}").raise_for_status()
    p = pockets(me, b["id"])[3]
    assert p["key"] == key and p["count"] == 1 and p["card"]["owned_id"] == copies[1]

    # the last one leaves: the pocket stays, empty, where it was
    me.delete(f"/api/binders/{b['id']}/cards/{copies[1]}").raise_for_status()
    ps = pockets(me, b["id"])
    assert len(ps) == 9 and ps[3]["key"] == key and ps[3]["blank"]
    me.delete(f"/api/binders/{b['id']}")


def test_arranging_moves_a_stack_as_one_pocket(me):
    b = me.post("/api/binders", json={"name": "Order", "kind": "custom", "pages": 1}).json()
    ps = pockets(me, b["id"])
    item, copies = three_of(me, "Movers")
    for cid in copies:
        me.put(f"/api/binders/{b['id']}/slots/{ps[0]['key']}", json={"owned_id": cid}).raise_for_status()
    _, other = a_card(me, "Neighbour")
    me.put(f"/api/binders/{b['id']}/slots/{ps[1]['key']}", json={"owned_id": other}).raise_for_status()

    # swap the first two pockets
    keys = [p["key"] for p in pockets(me, b["id"])]
    keys[0], keys[1] = keys[1], keys[0]
    me.put(f"/api/binders/{b['id']}/order", json={"slot_ids": [int(k) for k in keys]}).raise_for_status()

    after = pockets(me, b["id"])
    assert len(after) == 9
    assert after[1]["card"]["id"] == item and after[1]["count"] == 3   # the whole stack moved together
    assert after[0]["card"]["owned_id"] == other
    me.delete(f"/api/binders/{b['id']}")


def test_a_stack_survives_the_trip_through_a_backup(me):
    b = me.post("/api/binders", json={"name": "Carried", "kind": "custom", "pages": 1}).json()
    key = pockets(me, b["id"])[2]["key"]
    item, copies = three_of(me, "Travellers")
    for cid in copies:
        me.put(f"/api/binders/{b['id']}/slots/{key}", json={"owned_id": cid}).raise_for_status()

    blob = me.get("/api/backup/mine").content
    me.post("/api/backup/mine", files={"file": ("c.zip", blob, "application/zip")},
            data={"confirm": "RESTORE"}).raise_for_status()

    ps = pockets(me, b["id"])
    assert len(ps) == 9
    assert ps[2]["card"]["id"] == item and ps[2]["count"] == 3 and len(ps[2]["stack"]) == 2
    me.delete(f"/api/binders/{b['id']}")
