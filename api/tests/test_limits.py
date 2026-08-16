"""What a free account gets where somebody else pays for the server.

The argument these limits rest on is that the software is free and complete
— anybody may run it themselves and get every card and every binder, for
nothing, forever. So the property worth guarding above all others is that a
self-hosted install has no limits at all, and cannot grow one by accident.

The second is that a limit hides, never deletes. Somebody who lapses still
owns every card they filed.

    docker compose -f compose.test.yaml run --rm tests
"""

import os

import httpx
import pytest

from app import limits
from app.binder_view import MAX_DEX
from app.limits import binder_limit, card_limit, dex_ceiling, dex_limit, limited
from app.models import User
from app.plans import FREE, SUPPORTER

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def a_user(plan=FREE, is_admin=False):
    u = User(email="someone@example.com")
    u.plan = plan
    u.is_admin = is_admin
    return u


@pytest.fixture
def capped(monkeypatch):
    """An install that charges, with the numbers the service uses."""
    monkeypatch.setattr(limits.settings, "free_card_limit", 300)
    monkeypatch.setattr(limits.settings, "free_dex_limit", 151)
    monkeypatch.setattr(limits.settings, "free_binder_limit", 1)


# --- the install that must never grow a limit ------------------------------


def test_nothing_is_limited_by_default():
    """Every self-hosted install. The whole case for limiting the hosted one
    is that this stays true."""
    assert card_limit() == 0
    assert dex_limit() == 0
    assert binder_limit() == 0
    assert limited(a_user()) is False
    assert dex_ceiling(a_user()) == MAX_DEX


def test_this_stack_reports_no_limits(owner):
    s = owner.get("/api/settings").json()
    assert s["limits"]["applies"] is False
    assert s["limits"]["cards"] == 0
    assert s["limits"]["binders"] == 0


def test_a_full_pokedex_on_a_free_install(owner):
    """1,025 slots, which is what the Pokédex means."""
    assert dex_ceiling(a_user()) == MAX_DEX == 1025


# --- when an install does charge -------------------------------------------


def test_a_free_account_is_limited(capped):
    assert limited(a_user()) is True
    assert dex_ceiling(a_user()) == 151


def test_a_supporter_is_not(capped):
    who = a_user(plan=SUPPORTER)
    assert limited(who) is False
    assert dex_ceiling(who) == MAX_DEX, "a supporter lost the rest of the Pokédex"


def test_an_admin_is_not(capped):
    """Never billed, so never capped."""
    assert limited(a_user(is_admin=True)) is False


def test_the_ceiling_never_exceeds_the_real_dex(monkeypatch):
    """A number typed too large should not invent Pokémon."""
    monkeypatch.setattr(limits.settings, "free_card_limit", 300)
    monkeypatch.setattr(limits.settings, "free_dex_limit", 99999)
    assert dex_ceiling(a_user()) == MAX_DEX


def test_a_negative_number_is_treated_as_none(monkeypatch):
    monkeypatch.setattr(limits.settings, "free_card_limit", -5)
    monkeypatch.setattr(limits.settings, "free_dex_limit", -1)
    monkeypatch.setattr(limits.settings, "free_binder_limit", -1)
    assert card_limit() == dex_limit() == binder_limit() == 0
    assert limited(a_user()) is False


def test_limits_only_bite_where_something_is_set(monkeypatch):
    """Setting only the card cap must not silently cap binders too."""
    monkeypatch.setattr(limits.settings, "free_card_limit", 300)
    monkeypatch.setattr(limits.settings, "free_dex_limit", 0)
    monkeypatch.setattr(limits.settings, "free_binder_limit", 0)
    assert limited(a_user()) is True
    assert dex_ceiling(a_user()) == MAX_DEX, "the Pokédex shrank without being asked to"
    assert binder_limit() == 0


# --- the promise ------------------------------------------------------------


def test_a_limit_hides_and_never_deletes(owner):
    """There is no sweep, no cron, nothing that removes a row for being over
    a line. The only enforcement is at the moment of adding, and the Pokédex
    simply draws fewer slots — so a lapsed plan gives everything back the
    moment it is paid again, because nothing ever went anywhere.
    """
    import inspect

    from app.routers import collection

    source = inspect.getsource(collection.add_owned)
    assert "delete" not in source.lower(), "the card limit started deleting things"
    # it refuses the new one rather than making room
    assert "402" in source


def test_both_pokedex_builders_are_capped():
    """There are two of them, and the app asks the one in cards.py.

    Capping only binder_view._dex_entries looked like it worked — the tests
    passed, the code read correctly — and did nothing at all, because that is
    not the route the Pokédex page calls. Found by asking a running server
    how many slots it returned rather than by reading either file.
    """
    import inspect

    from app.binder_view import _dex_entries
    from app.routers.cards import pokedex

    for fn, where in ((_dex_entries, "binder_view"), (pokedex, "routers/cards")):
        assert "dex_ceiling" in inspect.getsource(fn),             f"the Pokédex builder in {where} is not capped"
