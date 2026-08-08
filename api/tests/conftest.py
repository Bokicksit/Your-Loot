"""Shared fixtures, and a guard.

Two of these tests destroy whatever database they are pointed at — that is
what restoring a backup *means*. Nothing stops somebody running the suite
against the install holding their actual collection except this file, so it
refuses unless the stack has been explicitly declared disposable.

Opting in is deliberate friction. `compose.test.yaml` sets it; nothing else
does.
"""

import os

import httpx
import pytest

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")

# Fixed rather than random so that whichever module runs first can claim the
# account and the rest can sign into it. Random credentials meant the first
# fixture to run locked every other one out, which showed up as a suite that
# quietly skipped most of itself.
OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "owner-password-1"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "destructive: wipes the database it runs against"
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LOOT_DESTRUCTIVE_OK") == "1":
        return
    skip = pytest.mark.skip(
        reason="destructive: set LOOT_DESTRUCTIVE_OK=1, and only on a stack you can lose"
    )
    for item in items:
        if "destructive" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def owner():
    """A signed-in owner, in either auth mode.

    Session-scoped and shared: it claims the account if nobody has, signs in
    if somebody already did, and skips only if the install belongs to a real
    person whose password we don't know.
    """
    c = httpx.Client(base_url=BASE, timeout=120)
    me = c.get("/api/auth/me").json()
    if not me["multi_user"]:
        yield c
        c.close()
        return
    if me.get("needs_setup"):
        c.post(
            "/api/auth/setup",
            json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
        ).raise_for_status()
    elif c.post(
        "/api/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    ).status_code != 200:
        pytest.skip("this install already belongs to somebody — run against a test stack")
    yield c
    c.close()
