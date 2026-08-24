"""Naming a card by showing it to the camera.

The catalogue already knows what twenty thousand cards look like, so the
question "which card is this" is arithmetic rather than a lookup — see
app/arthash.py. What this checks is the property that makes the feature
usable: a picture of a card finds that card, a picture of something else
finds nothing, and neither one ever reaches past the person asking.

    docker compose -f compose.test.yaml run --rm tests
"""

import io
import os
import uuid

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")

pytest.importorskip("PIL", reason="Pillow is what does the fingerprinting")


def _art(seed: int, size=(240, 336)) -> bytes:
    """A picture that is this card and no other.

    Deterministic from `seed` and deliberately full of structure: a
    fingerprint records which way brightness steps across the picture, so a
    flat colour would hash the same as every other flat colour and prove
    nothing. The blocks give it something to have an opinion about.
    """
    from PIL import Image

    im = Image.new("RGB", size)
    px = im.load()
    for x in range(size[0]):
        for y in range(size[1]):
            px[x, y] = (
                (x * 7 + seed * 53) % 256,
                (y * 5 + seed * 97) % 256,
                ((x + y) * 3 + seed * 31) % 256,
            )
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _photo(data: bytes) -> bytes:
    """The same picture as a camera would hand it over: resized, re-encoded
    lossily, a shade darker. If a fingerprint survives this it survives a
    phone, which is the whole claim."""
    from PIL import Image, ImageEnhance

    im = Image.open(io.BytesIO(data)).convert("RGB").resize((300, 420))
    im = ImageEnhance.Brightness(im).enhance(0.92)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return buf.getvalue()


@pytest.fixture
def scannable(owner):
    """A hand-made card with a fingerprint on it.

    Written straight onto the row rather than by running the seeder: the
    seeder's job is fetching twenty thousand pictures off a CDN, which is
    not a thing a test suite should do, and the part worth testing is what
    happens once a fingerprint exists.
    """
    import sys

    sys.path.insert(0, "/app")
    from app import arthash
    from app.db import SessionLocal
    from app.models import CardAttrs

    tag = uuid.uuid4().hex[:8]
    seed = int(tag[:4], 16)
    art = _art(seed)

    item = owner.post(
        "/api/cards", json={"title": f"Scanme {tag}", "card_number": "1"}
    ).json()

    db = SessionLocal()
    try:
        row = db.get(CardAttrs, item["id"])
        row.art_hash = arthash.to_signed(arthash.fingerprint(art))
        db.commit()
    finally:
        db.close()

    yield item, art
    owner.delete(f"/api/cards/{item['id']}")


def _scan(client: httpx.Client, data: bytes):
    return client.post(
        "/api/cards/scan",
        files={"file": ("scan.jpg", io.BytesIO(data), "image/jpeg")},
    )


def test_a_photograph_of_a_card_finds_that_card(owner, scannable):
    item, art = scannable
    r = _scan(owner, _photo(art))
    assert r.status_code == 200, r.text
    found = [c["id"] for c in r.json()["items"]]
    assert item["id"] in found, "the card did not recognise a photograph of itself"
    assert found[0] == item["id"], "the right card was not the closest match"


def test_a_picture_of_something_else_finds_nothing(owner, scannable):
    """The failure that matters. A scanner that always answers is worse than
    one that admits it does not know, because the wrong card added quietly is
    the one nobody notices."""
    item, _ = scannable
    r = _scan(owner, _photo(_art(0xBEEF)))
    assert r.status_code == 200, r.text
    assert item["id"] not in [c["id"] for c in r.json()["items"]]


def test_something_that_is_not_a_picture_is_refused(owner):
    r = _scan(owner, b"this is not an image, it is a sentence")
    assert r.status_code == 400
    assert r.json()["detail"], "refused without saying why"


def test_a_stranger_cannot_scan():
    """It reads the catalogue and costs CPU; both belong to people with an
    account on this server."""
    with httpx.Client(base_url=BASE, timeout=30) as anon:
        if not anon.get("/api/auth/me").json()["multi_user"]:
            pytest.skip("needs AUTH_MODE=multi")
        assert _scan(anon, _photo(_art(7))).status_code == 401
