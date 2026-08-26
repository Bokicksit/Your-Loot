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

# Fixed, and measured rather than picked. Swept across the art above and
# asserted against known distances, so a failure means the matcher changed
# rather than the dice:
#
#   ART_SEED   clean photo 1 bit, photographed on a table at an angle 0 bits
#   OTHER_SEED 43 bits from ART_SEED  (the match threshold is 12)
#
# This used to be `int(uuid[:4], 16)` — a different card every run — which
# passed locally, failed in CI, and passed again on a re-run. A test that
# picks its own difficulty at random is a coin flip wearing an assertion.
ART_SEED = 3
OTHER_SEED = 6


def _art(seed: int, size=(240, 336)) -> bytes:
    """A picture that is this card and no other.

    Built from a few broad gradients, which is the important part. Real card
    art is low-frequency — big smooth regions, a couple of strong shapes —
    and that is what survives being photographed at an angle and resampled
    back to nine pixels by eight. An earlier version of this used a grid of
    hard-edged blocks and was a far harsher subject than any real card: the
    edges aliased under rotation, and the test failed where actual cards
    matched at a distance of three. A stand-in has to be as forgiving as the
    thing it stands in for, or it tests the wrong feature.
    """
    import math

    from PIL import Image

    im = Image.new("RGB", size)
    px = im.load()
    w, h = size
    s = seed * 2654435761
    a1, a2, a3 = (s % 7) + 1, (s // 7 % 5) + 1, (s // 35 % 6) + 1
    p1, p2 = (s // 211 % 628) / 100, (s // 977 % 628) / 100
    for x in range(w):
        fx = x / w
        for y in range(h):
            fy = y / h
            v1 = math.sin(fx * a1 * 1.7 + p1) * math.cos(fy * a2 * 1.3 + p2)
            v2 = math.sin((fx + fy) * a3 * 1.1 + p1)
            px[x, y] = (
                int(128 + 110 * v1),
                int(128 + 100 * v2),
                int(128 + 95 * (v1 * 0.6 + v2 * 0.4)),
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
    art = _art(ART_SEED)

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
    r = _scan(owner, _photo(_art(OTHER_SEED)))
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
        assert _scan(anon, _photo(_art(ART_SEED))).status_code == 401


def _shifted(data: bytes) -> bytes:
    """The card off-centre in the frame with table around it — the shot the
    guide asked for and a hand didn't quite deliver."""
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    canvas = Image.new("RGB", (int(im.width * 1.18), int(im.height * 1.18)), (38, 38, 44))
    canvas.paste(im, (int(im.width * 0.14), int(im.height * 0.03)))
    buf = io.BytesIO()
    canvas.save(buf, "JPEG", quality=72)
    return buf.getvalue()


def _tilted(data: bytes) -> bytes:
    """The card a few degrees off level — the other way a hand holds it."""
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    im = im.rotate(4, resample=Image.BICUBIC, fillcolor=(38, 38, 44))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return buf.getvalue()


def test_an_imperfect_photograph_still_finds_the_card(owner, scannable):
    """The complaint that drove the probe jitter: a scan that only works on
    a perfectly framed, perfectly level card is a scan nobody's hands can
    use. The probe now reads the frame a dozen ways — nudged, tilted,
    cropped tighter — so each single honest mistake is survivable."""
    item, art = scannable
    for name, warp in (("shifted", _shifted), ("tilted", _tilted)):
        r = _scan(owner, warp(art))
        assert r.status_code == 200, r.text
        found = [c["id"] for c in r.json()["items"]]
        assert item["id"] in found, f"a {name} photograph lost the card"


def test_a_clean_photograph_is_sure_and_a_poor_one_is_not(owner, scannable):
    """The flag the camera acts on.

    The list stays generous — a person choosing between candidates wants the
    near misses — but the scanner is only allowed to decide by itself when
    the match is close enough that it cannot reasonably be the wrong card.
    Measured against 160 real cards: every auto-lock within ten bits was
    right; allowing twelve let badly framed shots through, wrong.
    """
    item, art = scannable

    r = _scan(owner, _photo(art))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"][0]["id"] == item["id"]
    assert body["sure"] is True, "a clean shot of a known card was not acted on"

    # nothing it has ever seen: not sure, and nothing offered
    r = _scan(owner, _photo(_art(OTHER_SEED)))
    assert r.json()["sure"] is False, "an unknown card came back confident"


def _on_a_table(data: bytes, rot: float = 8.0, dx: float = 0.06) -> bytes:
    """The shot somebody actually takes: the card a few degrees off straight,
    pushed off-centre, with table around it.

    This is the case the scanner used to lose. Measured over 565 real cards,
    a card tilted eight degrees and filling the frame scored 25 out of 60;
    with room around it and the corners found and squared up, 60 out of 60.
    """
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    table = Image.new("RGB", (int(w * 1.6), int(h * 1.6)), (92, 74, 58))
    table.paste(im, (int(w * (0.3 + dx)), int(h * 0.3)))
    table = table.rotate(rot, resample=Image.BICUBIC, fillcolor=(92, 74, 58))
    buf = io.BytesIO()
    table.save(buf, "JPEG", quality=72)
    return buf.getvalue()


def test_the_card_is_found_when_it_is_not_held_straight(owner, scannable):
    """The complaint this whole thing exists to answer.

    The matcher was always good at a card squared up and filling the frame,
    and that is not how anybody holds one. The photograph now has the card
    located and straightened before it is read, so being a few degrees off
    and a little off-centre stops mattering.
    """
    item, art = scannable
    r = _scan(owner, _on_a_table(art))
    assert r.status_code == 200, r.text
    found = [c["id"] for c in r.json()["items"]]
    assert item["id"] in found, "a card photographed on a table was lost"
    assert found[0] == item["id"], "the right card was not the closest match"


def test_a_photograph_with_no_card_in_it_is_not_straightened_into_one(owner):
    """The failure mode a detector invents: finding a card in a picture of a
    carpet, stretching it to card shape and asking the catalogue about it.
    Nothing should come back, and nothing should be confident."""
    from PIL import Image

    im = Image.new("RGB", (400, 500), (120, 118, 115))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    r = _scan(owner, buf.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["sure"] is False, "a blank picture came back confident"
