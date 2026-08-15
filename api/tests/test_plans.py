"""Who can open which collection, and what a paywall must never do.

Three properties matter more than the gate itself:

* a self-hosted install has no tiers at all — PAID_MODULES is empty there and
  nothing may become locked by accident;
* a lapsed account keeps every row it ever entered;
* backup and export are never behind the wall, because a collection you
  cannot leave with is not yours.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import plans
from app.models import User
from app.plans import FREE, SUPPORTER, costs_money, may_open, paid_modules, subscribed

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")


def a_user(**kw):
    u = User(email=kw.pop("email", "someone@example.com"), **kw)
    if u.plan is None:
        u.plan = FREE
    return u


# --- the install that must never grow a paywall ----------------------------


def test_nothing_costs_money_by_default():
    """Every self-hosted install. The person running it already paid, by
    running it, and a locked collection there would be nonsense."""
    assert paid_modules() == []
    for m in ("cards", "records", "books", "lego", "games"):
        assert not costs_money(m)
        assert may_open(a_user(plan=FREE), m), f"{m} was locked on a free install"


def test_this_stack_charges_for_nothing(owner):
    s = owner.get("/api/settings").json()
    assert s["paid_modules"] == [], "the test stack grew a paywall"

    for path in ("/api/records", "/api/books", "/api/lego"):
        r = owner.get(path, params={"limit": 1})
        assert r.status_code == 200, f"{path} was refused on an install that charges nothing"


# --- when an install does charge -------------------------------------------


@pytest.fixture
def charging(monkeypatch):
    monkeypatch.setattr(plans.settings, "paid_modules", "records,books,lego")


def test_free_accounts_are_refused_the_paid_ones(charging):
    free = a_user(plan=FREE)
    assert may_open(free, "cards"), "cards must stay free"
    for m in ("records", "books", "lego"):
        assert not may_open(free, m)


def test_a_supporter_gets_them(charging):
    who = a_user(plan=SUPPORTER)
    for m in ("cards", "records", "books", "lego"):
        assert may_open(who, m)


def test_a_plan_with_no_end_date_does_not_end(charging):
    """Granted by hand, or a lifetime one later. Null is not expired."""
    assert subscribed(a_user(plan=SUPPORTER, plan_until=None))


def test_a_lapsed_plan_closes_the_door(charging):
    yesterday = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    who = a_user(plan=SUPPORTER, plan_until=yesterday)
    assert not subscribed(who)
    assert not may_open(who, "records")
    assert may_open(who, "cards"), "lapsing must not touch the free collections"


def test_a_plan_that_still_has_time_works(charging):
    later = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3)
    assert subscribed(a_user(plan=SUPPORTER, plan_until=later))


def test_an_admin_is_not_billed(charging):
    """Somebody has to be able to look at the service they run."""
    assert subscribed(a_user(plan=FREE, is_admin=True))
    assert may_open(a_user(plan=FREE, is_admin=True), "records")


def test_an_unknown_plan_name_is_not_a_free_pass(charging):
    for junk in ("premium", "SUPPORTER ", "", None):
        assert not subscribed(a_user(plan=junk)), f"{junk!r} counted as paid"


# --- the promises ----------------------------------------------------------


def test_the_export_is_the_way_out_and_it_is_not_admin_only(owner):
    """Two different things live near each other and must not be confused.

    /api/backup is the whole database and is rightly admin-only — it is a
    server backup, not a personal one, and it holds everybody's collection.
    /api/share is one person's own collection and is what "take a copy" means
    for anybody who is not running the server.

    Written down because the first version of this test used an admin, which
    is exactly how you ship a promise that only holds for yourself.
    """
    scopes = owner.get("/api/share/cards")
    assert scopes.status_code == 200, "a person cannot export their own collection"


def test_an_export_ignores_the_paywall(charging):
    """The share route builds its lists by calling the list functions rather
    than by going back through the API, so the router's paywall does not
    apply to it — and that is right, not an oversight. Somebody whose plan
    lapsed must still be able to walk away with the records they entered.

    They can only export what they already added; adding is what the paywall
    stops. So there is nothing here to smuggle out.
    """
    from app.routers import share

    assert "records" in share.LISTS
    assert costs_money("records")
    # the guard lives on the router, and share never asks the router anything
    assert not any(
        getattr(d, "dependency", None) and "paywall" in repr(d.dependency)
        for d in (share.router.dependencies or [])
    ), "the export grew a paywall, which would trap somebody's collection"


def test_the_paywall_is_a_402_and_says_the_data_is_safe(charging):
    """The message a person actually reads. 402 rather than 403 because this
    is about payment, not permission, and the difference matters to anybody
    reading logs later."""
    from fastapi import HTTPException

    from app.main import _paywall

    guard = _paywall("records")
    with pytest.raises(HTTPException) as e:
        guard(user=a_user(plan=FREE))
    assert e.value.status_code == 402
    assert "still here" in e.value.detail
