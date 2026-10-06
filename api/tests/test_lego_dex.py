"""The LEGO Pokédex: every Pokémon LEGO has made, and which you have caught.

A capture is a Smart Tag tapped with a phone. The browser reads only the
tag's serial, so the first tap pairs it with a Pokémon and later taps capture.
Owning the set can count instead, behind a switch.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid

import pytest

BIDOOF_SERIAL = "3a:80:82:24:01:5c:16:e0"   # the real tile Bo read with NFC Tools


@pytest.fixture
def fresh(owner):
    """Start and finish with no tiles and the switch off."""
    def clear():
        page = owner.get("/api/lego/pokedex").json()
        for e in page["entries"]:
            for t in e["tiles"]:
                owner.delete(f"/api/lego/pokedex/tiles/{t['id']}")
        owner.put("/api/lego/pokedex/settings", json={"by_sets": False})
        for e in page["entries"]:
            if e.get("photo"):
                owner.put(f"/api/lego/pokedex/{e['dex_no']}/photo", json={"image_url": None})
    clear()
    yield
    clear()


def _entry(page, dex):
    return next(e for e in page["entries"] if e["dex_no"] == dex)


def test_every_lego_pokemon_is_listed_and_none_caught(owner, fresh):
    page = owner.get("/api/lego/pokedex").json()
    dex = [e["dex_no"] for e in page["entries"]]
    assert dex == sorted(dex)
    for n in (25, 399, 906, 132, 3):
        assert n in dex
    assert page["captured"] == 0 and not page["by_sets"]
    bidoof = _entry(page, 399)
    assert bidoof["name"] == "Bidoof" and bidoof["has_tile"]
    assert any(s["number"] == "72155" for s in bidoof["sets"])
    # the 18+ display sets come without Smart Tags
    assert not _entry(page, 3)["has_tile"]


def test_a_tile_is_paired_once_then_captures(owner, fresh):
    r = owner.post("/api/lego/pokedex/scan", json={"serial": BIDOOF_SERIAL})
    assert r.status_code == 200 and r.json() == {"known": False}
    assert owner.get("/api/lego/pokedex").json()["captured"] == 0, "a scan alone writes nothing"

    r = owner.post("/api/lego/pokedex/tiles", json={"serial": BIDOOF_SERIAL, "dex_no": 399})
    assert r.status_code == 201, r.text
    bidoof = _entry(r.json()["pokedex"], 399)
    assert bidoof["captured"] and bidoof["how"] == "tile" and len(bidoof["tiles"]) == 1
    # the serial identifies a physical object and is never sent back
    assert BIDOOF_SERIAL.replace(":", "") not in r.text

    # the same tile, written another way, is recognised
    r = owner.post("/api/lego/pokedex/scan", json={"serial": "3A-80-82-24-01-5C-16-E0"})
    assert r.json()["known"] is True and r.json()["name"] == "Bidoof"

    # a wrong first answer is put right by pairing again, not by a second row
    owner.post("/api/lego/pokedex/tiles", json={"serial": BIDOOF_SERIAL, "dex_no": 1})
    page = owner.get("/api/lego/pokedex").json()
    assert not _entry(page, 399)["captured"] and _entry(page, 1)["captured"]
    assert page["captured"] == 1


def test_forgetting_a_tile_uncaptures(owner, fresh):
    page = owner.post(
        "/api/lego/pokedex/tiles", json={"serial": "e016aa0011223344", "dex_no": 25}
    ).json()["pokedex"]
    tile = _entry(page, 25)["tiles"][0]["id"]
    page = owner.delete(f"/api/lego/pokedex/tiles/{tile}").json()
    assert not _entry(page, 25)["captured"]
    assert owner.delete(f"/api/lego/pokedex/tiles/{tile}").status_code == 404


def test_a_pokemon_lego_has_not_listed_yet_can_still_be_caught(owner, fresh):
    page = owner.post(
        "/api/lego/pokedex/tiles", json={"serial": "e016bb0011223344", "dex_no": 448}
    ).json()["pokedex"]
    lucario = _entry(page, 448)
    assert lucario["captured"] and lucario["sets"] == []


def test_owning_the_set_counts_only_when_switched_on(owner, fresh):
    item = owner.post(
        "/api/lego", json={"title": f"Venusaur, Charizard and Blastoise {uuid.uuid4().hex[:4]}",
                           "set_number": "72153-1"},
    ).json()["id"]
    owner.post(f"/api/items/{item}/owned", json={}).raise_for_status()
    try:
        page = owner.get("/api/lego/pokedex").json()
        assert not _entry(page, 9)["captured"], "scan-only by default"
        assert any(s["owned"] for s in _entry(page, 9)["sets"])

        page = owner.put("/api/lego/pokedex/settings", json={"by_sets": True}).json()
        assert page["by_sets"]
        for n in (3, 6, 9):
            assert _entry(page, n)["captured"] and _entry(page, n)["how"] == "set"
        assert not _entry(page, 399)["captured"]
    finally:
        owner.delete(f"/api/lego/{item}")


def test_a_serial_has_to_be_a_serial(owner, fresh):
    r = owner.post("/api/lego/pokedex/scan", json={"serial": "not a tag at all"})
    assert r.status_code == 422
    r = owner.post("/api/lego/pokedex/tiles", json={"serial": BIDOOF_SERIAL, "dex_no": 9999})
    assert r.status_code == 422


def test_pictures_are_lego_not_cards(owner, fresh):
    """A box picture from Rebrickable until you photograph your own build."""
    page = owner.get("/api/lego/pokedex").json()
    bidoof = _entry(page, 399)
    assert bidoof["art"] == "https://cdn.rebrickable.com/media/sets/72155-1.jpg"
    assert bidoof["photo"] is None
    # a Pokémon in a tagged set and a display set shows the tagged one
    assert _entry(page, 6)["art"].endswith("/72167-1.jpg")

    page = owner.put("/api/lego/pokedex/399/photo", json={"image_url": "/images/my-bidoof.jpg"}).json()
    assert _entry(page, 399)["art"] == "/images/my-bidoof.jpg"
    assert _entry(page, 1)["art"].endswith("/72155-1.jpg"), "Bulbasaur keeps the box"

    page = owner.put("/api/lego/pokedex/399/photo", json={"image_url": None}).json()
    assert _entry(page, 399)["art"].endswith("/72155-1.jpg")
    assert owner.put("/api/lego/pokedex/0/photo", json={"image_url": None}).status_code == 404

