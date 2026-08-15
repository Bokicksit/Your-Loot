"""Is a collection this install does not carry actually gone?

Two catalogues forbid commercial use outright, so the hosted service cannot
offer movies or comics at all. Hiding the tab is not enough — a collection
absent from the UI but still answering on /api/movies has not been removed,
it has been moved somewhere only the curious look.

The invite-only test stack carries everything, exactly like a self-hosted
install, which is the property most worth protecting: none of this may
change what a self-hoster gets.

    docker compose -f compose.test.yaml run --rm tests
"""

import os

import httpx
import pytest

from app.modules import ALL, available, offers

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def test_the_default_is_every_collection():
    """Empty means all of them. Every install before this setting existed had
    all eight, and upgrading into it must not take any away."""
    assert available() == ALL
    for m in ALL:
        assert offers(m), f"{m} vanished from a default install"


@pytest.mark.parametrize("setting,expected", [
    ("cards,records,books,lego", ["cards", "books", "records", "lego"]),
    ("cards", ["cards"]),
    ("  CARDS , Records ", ["cards", "records"]),
    ("", ALL),
    ("   ", ALL),
])
def test_the_setting_is_read_leniently(monkeypatch, setting, expected):
    """Case and spacing are how people actually type a list into a form, and
    the answer comes back in the app's own order rather than theirs — the tab
    bar should not reorder itself because somebody typed lego first."""
    from app import modules
    monkeypatch.setattr(modules.settings, "available_modules", setting)
    assert modules.available() == expected


def test_an_unknown_name_costs_that_name_and_nothing_else(monkeypatch):
    """A typo should lose you one collection, not stop the server booting."""
    from app import modules
    monkeypatch.setattr(modules.settings, "available_modules", "cards,recrods,books")
    assert modules.available() == ["cards", "books"]


def test_this_stack_still_serves_everything(owner):
    """The suite's API sets nothing, so it stands in for every self-hosted
    install: all eight collections answer, and settings says so."""
    s = owner.get("/api/settings").json()
    assert set(s["available_modules"]) == set(ALL)

    for path in ("/api/movies", "/api/comics", "/api/books", "/api/records", "/api/lego"):
        r = owner.get(path, params={"limit": 1})
        assert r.status_code == 200, f"{path} answered {r.status_code} on a full install"


def test_settings_never_offers_a_collection_the_server_lacks(owner):
    """enabled_modules is chosen from available_modules, so it can never
    contain something this install does not carry."""
    s = owner.get("/api/settings").json()
    assert set(s["enabled_modules"]) <= set(s["available_modules"])

    # asking for one anyway does not smuggle it in
    before = s["enabled_modules"]
    r = owner.put("/api/settings", json={"enabled_modules": ["cards", "nonsense"]})
    r.raise_for_status()
    try:
        assert "nonsense" not in r.json()["enabled_modules"]
    finally:
        owner.put("/api/settings", json={"enabled_modules": before}).raise_for_status()
