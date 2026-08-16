"""Can a stranger look at somebody's photographs?

These are pictures of a person's own things — the shelf, the sleeve, the
graded slab with their name printed on it. They used to be served by a static
mount, which is to say to anybody at all who had the URL, forever.

The filenames are random hex, so this was never enumerable. But obscurity is
not access control, and "nobody will guess it" stops being reassuring the
moment a URL appears in a browser history, a proxy log or a shared screen.

    docker compose -f compose.test.yaml run --rm tests
"""

import io
import os
import time
import uuid

import httpx
import pytest

from app.imgauth import DEFAULT_TTL, sign, verify

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001r0dda8db0000000049454e44ae426082"
    .replace("r", "0")
)


@pytest.fixture
def uploaded(owner):
    """A real photograph on the server, removed afterwards."""
    r = owner.post(
        "/api/images",
        files={"file": (f"{uuid.uuid4().hex[:8]}.png", io.BytesIO(PNG), "image/png")},
    )
    if r.status_code != 200:
        pytest.skip(f"could not upload a test image ({r.status_code}: {r.text[:80]})")
    url = r.json()["url"]
    yield url.rsplit("/", 1)[-1]


# --- the signature, on its own ---------------------------------------------


def test_a_fresh_token_is_accepted():
    assert verify("photo.png", sign("photo.png")) is True


def test_a_token_for_one_photo_does_not_open_another():
    """The filename is inside the signature, so a link somebody was given
    legitimately is not a key to everything else."""
    assert verify("theirs.png", sign("mine.png")) is False


def test_an_expired_token_is_refused():
    old = sign("photo.png", ttl=-10)
    assert verify("photo.png", old) is False


def test_a_token_expires_when_it_says_it_does():
    now = time.time()
    token = sign("photo.png", ttl=DEFAULT_TTL, now=now)
    assert verify("photo.png", token, now=now + DEFAULT_TTL - 5) is True
    assert verify("photo.png", token, now=now + DEFAULT_TTL + 5) is False


def test_a_token_whose_expiry_was_edited_is_refused():
    """The obvious attack: take a real token and push the date out."""
    token = sign("photo.png", ttl=-10)
    _, _, mac = token.partition(".")
    forged = f"{int(time.time()) + 9999}.{mac}"
    assert verify("photo.png", forged) is False


@pytest.mark.parametrize("token", [None, "", "nonsense", "123", "abc.def", ".", "1.", "."])
def test_a_malformed_token_is_refused(token):
    assert verify("photo.png", token) is False


# --- the route -------------------------------------------------------------


def test_a_stranger_cannot_fetch_a_photograph(uploaded):
    """Signed out, no token. This is the whole point of the change."""
    r = httpx.get(f"{BASE}/images/{uploaded}", timeout=60)
    assert r.status_code == 404, (
        f"a photograph was served to nobody ({r.status_code})"
    )


def test_a_refusal_does_not_admit_the_file_exists(uploaded):
    """404 and not 403. A 403 tells somebody guessing filenames that they
    guessed right, which is most of what they wanted to know."""
    there = httpx.get(f"{BASE}/images/{uploaded}", timeout=60)
    not_there = httpx.get(f"{BASE}/images/{uuid.uuid4().hex}.png", timeout=60)
    assert there.status_code == not_there.status_code == 404


def test_a_signed_link_works_without_any_session(uploaded):
    """What a phone app uses: an `<img>` cannot send a bearer token, so the
    URL has to carry its own proof."""
    r = httpx.get(f"{BASE}/images/{uploaded}", params={"token": sign(uploaded)}, timeout=60)
    assert r.status_code == 200
    assert r.content, "the file came back empty"


def test_a_signed_in_person_needs_no_token(owner, uploaded):
    """The app's own path — every `<img>` in it carries the session cookie,
    which is why no URL anywhere had to be rewritten."""
    assert owner.get(f"/images/{uploaded}").status_code == 200


def test_a_signed_link_can_be_asked_for(owner, uploaded):
    r = owner.get("/api/images/link", params={"name": uploaded})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith(f"/images/{uploaded}?token=")
    assert httpx.get(f"{BASE}{body['url']}", timeout=60).status_code == 200


@pytest.mark.parametrize("attack", [
    "../alembic.ini", "..%2F..%2Fetc%2Fpasswd", "....//alembic.ini", ".env",
])
def test_the_route_cannot_be_walked_out_of(owner, attack):
    """It reads a filename off the URL and joins it to a directory, which is
    the shape of every directory-traversal bug ever written."""
    r = owner.get(f"/images/{attack}")
    assert r.status_code == 404, f"{attack!r} answered {r.status_code}"
    assert b"sqlalchemy" not in r.content.lower()
