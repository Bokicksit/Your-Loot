"""Hardware knows what kind of thing it is: console, controller, accessory.

A fixed vocabulary, so the filter stays three choices — plus "unsorted",
which is every row made before kinds existed, on purpose: guessed backfill
is how databases rot, and two clicks in the editor is the honest fix.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid


def test_a_kind_is_kept_filtered_and_changed(owner):
    mark = uuid.uuid4().hex[:6]
    made = owner.post("/api/games", json={
        "title": f"Wavebird {mark}", "is_hardware": True,
        "hardware_kind": "controller",
    }).json()
    try:
        assert made["attrs"]["hardware_kind"] == "controller"
        owner.post(f"/api/items/{made['id']}/owned",
                   json={"condition": "Good", "completeness": "loose"}).raise_for_status()

        hits = owner.get("/api/games", params={
            "is_hardware": True, "hardware_kind": "controller", "search": mark,
        }).json()
        assert any(i["id"] == made["id"] for i in hits["items"])

        # and not among the consoles
        hits = owner.get("/api/games", params={
            "is_hardware": True, "hardware_kind": "console", "search": mark,
        }).json()
        assert not any(i["id"] == made["id"] for i in hits["items"])

        moved = owner.patch(f"/api/games/{made['id']}",
                            json={"hardware_kind": "accessory"}).json()
        assert moved["attrs"]["hardware_kind"] == "accessory"
    finally:
        owner.delete(f"/api/games/{made['id']}")


def test_unsorted_is_a_real_answer(owner):
    """Rows made before kinds existed have none, and the filter has to be
    able to find them — they are the ones waiting to be sorted."""
    mark = uuid.uuid4().hex[:6]
    made = owner.post("/api/games", json={
        "title": f"Mystery Box {mark}", "is_hardware": True,
    }).json()
    try:
        assert made["attrs"]["hardware_kind"] is None
        owner.post(f"/api/items/{made['id']}/owned",
                   json={"condition": "Good"}).raise_for_status()
        hits = owner.get("/api/games", params={
            "is_hardware": True, "hardware_kind": "unsorted", "search": mark,
        }).json()
        assert any(i["id"] == made["id"] for i in hits["items"])
    finally:
        owner.delete(f"/api/games/{made['id']}")


def test_a_made_up_kind_is_refused(owner):
    r = owner.post("/api/games", json={
        "title": "Gizmo", "is_hardware": True, "hardware_kind": "gizmo",
    })
    assert r.status_code == 422
