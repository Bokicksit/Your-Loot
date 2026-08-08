"""The brake on guessing, and the lock on a one-person install."""

import os
import uuid

import httpx
import pytest

from app.ratelimit import Attempts

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
# a second stack running the default mode, where the single-user lock lives
SOLO = os.environ.get("LOOT_SOLO_URL")


# --- the brake itself, no HTTP involved -------------------------------------

def test_it_takes_the_stated_number_of_wrong_answers():
    a = Attempts(limit=3, window=60)
    for _ in range(3):
        assert a.retry_after("k") == 0
        a.failed("k")
    assert a.retry_after("k") > 0


def test_getting_it_right_forgives_the_near_misses():
    """Somebody mistyping their own password twice and then getting it right
    must not be a step closer to being locked out."""
    a = Attempts(limit=3, window=60)
    a.failed("k")
    a.failed("k")
    a.succeeded("k")
    for _ in range(3):
        assert a.retry_after("k") == 0
        a.failed("k")


def test_one_person_failing_does_not_lock_out_another():
    a = Attempts(limit=2, window=60)
    a.failed("alice")
    a.failed("alice")
    assert a.retry_after("alice") > 0
    assert a.retry_after("bob") == 0


def test_the_window_expires():
    a = Attempts(limit=1, window=0)  # everything is already old
    a.failed("k")
    assert a.retry_after("k") == 0


def test_it_cannot_grow_without_bound():
    """A spray across thousands of names shouldn't be a memory leak."""
    a = Attempts(limit=5, window=0, ceiling=16)
    for i in range(200):
        a.failed(f"key-{i}")
    assert len(a._hits) <= 64


# --- the wiring, through the API --------------------------------------------

def test_repeated_wrong_passwords_start_being_refused():
    with httpx.Client(base_url=BASE, timeout=30) as c:
        if not c.get("/api/auth/me").json()["multi_user"]:
            pytest.skip("needs AUTH_MODE=multi")
        who = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
        codes = [
            c.post("/api/auth/login", json={"email": who, "password": "wrong-one-11"}).status_code
            for _ in range(6)
        ]
    assert codes[:5] == [401] * 5, f"expected five refusals first, got {codes}"
    assert codes[5] == 429, f"the sixth attempt should be throttled, got {codes[5]}"


@pytest.mark.skipif(not SOLO, reason="no single-user stack to test against")
def test_a_solo_install_can_be_locked_and_unlocked():
    """The Radarr-style lock: one account, no email, a password or a PIN —
    and no login screen at all until you ask for one."""
    with httpx.Client(base_url=SOLO, timeout=30) as c:
        assert c.get("/api/settings").status_code == 200, "should open freely to start with"
        assert c.get("/api/auth/me").json()["locked"] is False

        pin = "4821"
        c.post("/api/auth/password", json={"new_password": pin}).raise_for_status()

        with httpx.Client(base_url=SOLO, timeout=30) as stranger:
            assert stranger.get("/api/settings").status_code == 401, "the lock did nothing"
            assert stranger.get("/api/auth/me").json()["locked"] is True
            assert stranger.post(
                "/api/auth/login", json={"password": "0000"}
            ).status_code == 401
            stranger.post("/api/auth/login", json={"password": pin}).raise_for_status()
            assert stranger.get("/api/settings").status_code == 200

            # and taking it off again is as easy as putting it on
            stranger.post(
                "/api/auth/password", json={"current_password": pin, "new_password": None}
            ).raise_for_status()

        assert c.get("/api/settings").status_code == 200, "the lock did not come off"
