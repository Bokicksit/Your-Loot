"""Games credit IGDB where IGDB supplied them.

The partnership asks for user-facing attribution beside their data, linking
the game on their site. Their URLs are built from a slug, so the credit only
exists if the slug was kept at the moment the game was added — which is the
part a schema change can silently drop.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid


def test_a_game_from_igdb_keeps_the_address_of_its_page(owner):
    mark = uuid.uuid4().hex[:6]
    game = owner.post("/api/games", json={
        "title": f"Credited {mark}",
        "igdb_id": 1020,
        "igdb_slug": "grand-theft-auto-v",
    }).json()
    try:
        assert game["attrs"]["igdb_slug"] == "grand-theft-auto-v", (
            "the link back to IGDB was not kept"
        )
        # owned, because a shelf is what you have a copy of — an entry with
        # none is not on the list the page reads from
        owner.post(
            f"/api/items/{game['id']}/owned", json={"condition": "Good"}
        ).raise_for_status()
        # and it survives a re-read, which is what the page actually renders
        again = owner.get("/api/games", params={"search": mark, "limit": 5}).json()
        row = next(g for g in again["items"] if g["id"] == game["id"])
        assert row["attrs"]["igdb_slug"] == "grand-theft-auto-v"
    finally:
        owner.delete(f"/api/games/{game['id']}")


def test_a_hand_typed_game_credits_nobody(owner):
    """A game nobody supplied has nothing to attribute, and a link to
    somebody else's page would be worse than no link at all."""
    mark = uuid.uuid4().hex[:6]
    game = owner.post("/api/games", json={"title": f"Typed {mark}"}).json()
    try:
        assert game["attrs"]["igdb_slug"] is None
        assert game["source"] if "source" in game else True
    finally:
        owner.delete(f"/api/games/{game['id']}")
