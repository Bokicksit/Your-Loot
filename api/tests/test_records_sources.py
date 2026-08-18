"""Records say where they came from, because Discogs requires it said.

Their API terms put two obligations on any application, personal or
commercial: a "Data provided by Discogs" credit next to the data, linking the
release page — which needs the release id stored, not just used — and no
commercial use of release images, which are Restricted Data where the
metadata is CC0.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid


def test_a_record_keeps_the_identity_of_where_it_came_from(owner):
    """The row is stamped with the truth. It used to say "musicbrainz" for
    anything with a barcode — Discogs picks and shop listings included —
    which is a lie the attribution link would have repeated, and it left a
    personal restore nothing to match the pressing on."""
    mark = uuid.uuid4().hex[:6]

    picked = owner.post("/api/records", json={
        "title": f"Discogs Pick {mark}", "artist": "Somebody",
        "discogs_id": 249504,
    }).json()
    typed = owner.post("/api/records", json={
        "title": f"Hand Typed {mark}", "artist": "Somebody Else",
    }).json()
    try:
        assert picked["source"] == "discogs"
        assert picked["external_id"] == "249504", "the release id was not kept"
        assert typed["source"] == "manual"
        assert typed["external_id"] is None
    finally:
        owner.delete(f"/api/records/{picked['id']}")
        owner.delete(f"/api/records/{typed['id']}")


def test_a_musicbrainz_pick_is_not_credited_to_discogs(owner):
    mark = uuid.uuid4().hex[:6]
    row = owner.post("/api/records", json={
        "title": f"MB Pick {mark}",
        "mbid": "76df3287-6cda-33eb-8e9a-044b5e15ffdd",
    }).json()
    try:
        assert row["source"] == "musicbrainz"
        assert row["external_id"] == "76df3287-6cda-33eb-8e9a-044b5e15ffdd"
    finally:
        owner.delete(f"/api/records/{row['id']}")
