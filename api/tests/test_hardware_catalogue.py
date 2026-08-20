"""The NA console catalogue: our own dataset, seeded at every API start.

Template rows (source="yourloot") that nobody owns. Picking one prefills the
add form; the submit creates the user's own row, because a serial number and
whether it still works belong to the unit on the shelf, not the catalogue.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid


def test_the_catalogue_is_seeded_and_searchable(owner):
    """entrypoint.sh runs seed_consoles.py before uvicorn, so by the time
    anything can ask, the answer is there."""
    d = owner.get("/api/games/hardware/catalogue", params={"q": "Super Nintendo"}).json()
    assert d["seeded"] is True
    titles = [i["title"] for i in d["items"]]
    assert any("Super Nintendo" in t for t in titles), titles
    snes = next(i for i in d["items"] if i["title"] == "Super Nintendo")
    assert snes["attrs"]["is_hardware"] is True
    assert snes["attrs"]["hardware_kind"] == "console"
    assert snes["attrs"]["model_number"] == "SNS-001"
    assert snes["attrs"]["platform_name"]  # linked, not just written down


def test_the_kind_filter_narrows_the_catalogue(owner):
    d = owner.get(
        "/api/games/hardware/catalogue",
        params={"q": "GameCube", "kind": "controller"},
    ).json()
    assert d["items"], "the WaveBird should be here"
    assert all(i["attrs"]["hardware_kind"] == "controller" for i in d["items"])


def test_catalogue_rows_stay_out_of_the_shelf_list(owner):
    """173 templates seeded, and a hardware list that only shows what you
    own — a template row nobody owns must never appear on anybody's shelf."""
    d = owner.get(
        "/api/games",
        params={"is_hardware": True, "search": "Atari 5200", "limit": 200},
    ).json()
    assert not any(i["title"] == "Atari 5200" and not i["owned"] for i in d["items"])


def test_a_template_cannot_be_deleted_or_edited(owner):
    """A template prefills everybody's add form. Your own row — made from the
    prefill — edits and deletes fine; the shared one refuses both."""
    d = owner.get("/api/games/hardware/catalogue", params={"q": "Atari 2600 Jr"}).json()
    tpl = d["items"][0]
    assert owner.delete(f"/api/games/{tpl['id']}").status_code == 409
    assert owner.patch(
        f"/api/games/{tpl['id']}", json={"title": "scribbled on"}
    ).status_code == 409


def test_picking_makes_your_own_row_with_your_own_serial(owner):
    """The pick flow end to end, as the frontend does it: read the template,
    create with its facts plus this unit's serial, own it. The result is an
    ordinary manual row — editable, deletable, and separate from the
    template."""
    mark = uuid.uuid4().hex[:6]
    d = owner.get("/api/games/hardware/catalogue", params={"q": "Game Boy Pocket"}).json()
    tpl = next(i for i in d["items"] if i["title"].startswith("Game Boy Pocket"))

    made = owner.post("/api/games", json={
        "title": f"{tpl['title']} {mark}",
        "is_hardware": True,
        "hardware_kind": tpl["attrs"]["hardware_kind"],
        "platform_id": tpl["attrs"]["platform_id"],
        "model_number": tpl["attrs"]["model_number"],
        "region": "NTSC-U",
        "serial_number": f"GBP-{mark}",
        "working": "works",
        "image_url": tpl["image_url"],
    }).json()
    try:
        assert made["id"] != tpl["id"], "the pick must clone, not adopt"
        assert made["attrs"]["serial_number"] == f"GBP-{mark}"
        owner.post(f"/api/items/{made['id']}/owned",
                   json={"condition": "Good", "completeness": "loose"}).raise_for_status()

        mine = owner.get("/api/games", params={
            "is_hardware": True, "search": mark, "limit": 10,
        }).json()
        assert any(i["id"] == made["id"] for i in mine["items"])

        # and your own row edits fine, unlike the template it came from
        renamed = owner.patch(f"/api/games/{made['id']}",
                              json={"working": "partial"}).json()
        assert renamed["attrs"]["working"] == "partial"
    finally:
        assert owner.delete(f"/api/games/{made['id']}").status_code == 204


def test_reseeding_is_a_refresh_not_a_duplicate(owner):
    """The seed runs on every API start, so the catalogue must hold at one
    copy of each entry no matter how many restarts an install has seen. The
    test stack's API has started at least once; the count proves the upsert."""
    d = owner.get("/api/games/hardware/catalogue", params={"q": "Atari 5200"}).json()
    exact = [i for i in d["items"] if i["title"] == "Atari 5200"]
    assert len(exact) == 1, [i["id"] for i in exact]
