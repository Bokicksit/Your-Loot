"""Three holes the security pass found, and the proof they are shut.

They have nothing in common except that each one is invisible from the
outside: the app behaves identically whether or not they are fixed, right up
until somebody uses them. That is exactly the kind of thing that rots, so it
is pinned here rather than trusted to stay fixed.

Pure functions and no network — every one of these is a decision the code
makes before it talks to anybody, which is the only reason they are testable
at all.

    docker compose -f compose.test.yaml run --rm tests
"""

import socket
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/app")

from app import ratelimit  # noqa: E402
from app.config import settings  # noqa: E402
from app.routers import images  # noqa: E402


class FakeRequest:
    """Just the two things client_address looks at."""

    def __init__(self, peer, forwarded=None):
        self.client = type("C", (), {"host": peer})() if peer else None
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


@pytest.fixture
def hops(monkeypatch):
    def set_to(n):
        monkeypatch.setattr(settings, "trusted_proxies", n)
    return set_to


# ---------------------------------------------------------------- who you are

def test_a_spoofed_forwarded_header_does_not_change_the_address(hops):
    """The bug, stated as a test.

    nginx appends the address it saw to the right of whatever arrived. So a
    caller writing their own X-Forwarded-For is writing the *left* of the
    list, and reading the left — which is what this used to do — meant a
    different bucket for every request and no rate limit at all.
    """
    hops(1)
    real = "203.0.113.9"
    spoofed = FakeRequest("10.0.0.2", f"1.2.3.4, 5.6.7.8, {real}")
    honest = FakeRequest("10.0.0.2", real)
    assert ratelimit.client_address(spoofed) == real
    assert ratelimit.client_address(honest) == real


def test_the_whole_brake_survives_a_header_that_changes_every_request(hops):
    """The consequence: a hundred tries from one address is still a hundred."""
    hops(1)
    attempts = ratelimit.Attempts(limit=5, window=300)
    for i in range(100):
        req = FakeRequest("10.0.0.2", f"9.9.9.{i % 250}, 203.0.113.9")
        key = ratelimit.client_key(req, "victim@example.com")
        attempts.failed(key)
    req = FakeRequest("10.0.0.2", "203.0.113.9")
    assert attempts.retry_after(ratelimit.client_key(req, "victim@example.com"))


def test_two_proxies_means_counting_in_two(hops):
    """Cloudflare or a tunnel in front of nginx: the client is one further in."""
    hops(2)
    req = FakeRequest("10.0.0.2", "1.2.3.4, 203.0.113.9, 172.16.0.5")
    assert ratelimit.client_address(req) == "203.0.113.9"


def test_no_proxy_means_the_header_is_ignored(hops):
    hops(0)
    req = FakeRequest("203.0.113.9", "1.2.3.4")
    assert ratelimit.client_address(req) == "203.0.113.9"


def test_a_short_or_junk_chain_falls_back_to_the_socket(hops):
    """Either one means the header was not written by the proxies it claims."""
    hops(2)
    assert ratelimit.client_address(FakeRequest("10.0.0.2", "1.2.3.4")) == "10.0.0.2"
    hops(1)
    assert ratelimit.client_address(FakeRequest("10.0.0.2", "not-an-ip")) == "10.0.0.2"
    # a value with the key separator in it must never reach the key
    assert "|" not in ratelimit.client_address(FakeRequest("10.0.0.2", "a|b"))


def test_an_address_alone_still_names_a_bucket(hops):
    hops(1)
    req = FakeRequest("10.0.0.2", "203.0.113.9")
    assert ratelimit.client_key(req, "Someone@Example.com ") == "203.0.113.9|someone@example.com"


# ------------------------------------------------------- what searching costs

class FakeUser:
    def __init__(self, id):
        self.id = id


@pytest.fixture(autouse=True)
def fresh_budget():
    ratelimit.lookups._hits.clear()
    yield
    ratelimit.lookups._hits.clear()


def test_a_search_loop_is_stopped_before_it_reaches_the_provider():
    limit = ratelimit.lookups.limit
    for _ in range(limit):
        ratelimit.outbound(user=FakeUser(1))
    with pytest.raises(HTTPException) as e:
        ratelimit.outbound(user=FakeUser(1))
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers


def test_the_budget_belongs_to_the_account_not_the_network():
    """Signing in from somewhere else must not hand out a second helping —
    the quota being spent is the server's API keys, and the account is who
    spent it."""
    for _ in range(ratelimit.lookups.limit):
        ratelimit.outbound(user=FakeUser(1))
    ratelimit.outbound(user=FakeUser(2))  # a different person is unaffected
    with pytest.raises(HTTPException):
        ratelimit.outbound(user=FakeUser(1))


# every route that spends somebody else's quota, named so that adding one
# without a brake is a failing test rather than a bill
CHARGED = [
    ("app.routers.books", "/search"),
    ("app.routers.books", "/description"),
    ("app.routers.cards", "/tcgdex/search"),
    ("app.routers.cards", "/tcgdex/{card_id}"),
    ("app.routers.comics", "/runs"),
    ("app.routers.comics", "/search"),
    ("app.routers.games", "/boxart"),
    ("app.routers.games", "/igdb/search"),
    ("app.routers.lego", "/search"),
    ("app.routers.lookup", "/barcode"),
    ("app.routers.lookup", "/products"),
    ("app.routers.movies", "/tmdb/search"),
    ("app.routers.records", "/search"),
    ("app.routers.records", "/tracklist"),
]


@pytest.mark.parametrize("module,path", CHARGED)
def test_every_third_party_search_is_charged(module, path):
    import importlib

    router = importlib.import_module(module).router
    full = router.prefix + path
    route = next((r for r in router.routes if r.path == full), None)
    assert route is not None, f"no route at {full}"
    names = [d.dependency.__name__ for d in route.dependencies]
    assert "outbound" in names, f"{full} calls out without a rate limit"


# ------------------------------------------------------------ where it dials

def fake_client(monkeypatch, respond):
    """Stand in for httpx.Client and record what each hop was asked to do."""
    calls = []

    class Client:
        def __init__(self, **kw):
            self.opened = kw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            calls.append({"url": url, **kw, "client": self.opened})
            return respond(len(calls) - 1)

    monkeypatch.setattr(images.httpx, "Client", Client)
    return calls


def reply(is_redirect=False, location=None):
    return type("R", (), {
        "is_redirect": is_redirect,
        "headers": {"location": location} if location else {},
    })()


def test_a_host_that_resolves_into_the_lan_is_refused(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))],
    )
    with pytest.raises(HTTPException) as e:
        images._safe_address("metadata.example.com")
    assert e.value.status_code == 400


def test_the_fetch_dials_the_address_that_was_cleared(monkeypatch):
    """The rebinding case.

    The old guard approved a *name* and then let httpx look it up again,
    leaving a gap the other side controls: answer publicly for the check,
    answer 127.0.0.1 for the fetch. Here the second answer is deliberately
    hostile, and it must not matter — the request has to go to the address
    that passed.
    """
    answers = iter([
        [(2, 1, 6, "", ("93.184.216.34", 0))],   # the check sees this
        [(2, 1, 6, "", ("127.0.0.1", 0))],     # anything after would see this
    ])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: next(answers))

    calls = fake_client(monkeypatch, lambda i: reply())
    images._checked_get("https://art.example.com/card.png")

    seen = calls[0]
    assert seen["url"] == "https://93.184.216.34/card.png"
    # the name still travels, so virtual hosts and certificates work
    assert seen["headers"]["Host"] == "art.example.com"
    assert seen["extensions"]["sni_hostname"] == "art.example.com"
    assert seen["client"]["follow_redirects"] is False


def test_a_redirect_is_resolved_against_the_name_not_the_pin(monkeypatch):
    """A relative Location has to mean what the server meant by it, and the
    next hop gets checked from scratch."""
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    calls = fake_client(
        monkeypatch,
        lambda i: reply(True, "/moved.png") if i == 0 else reply(),
    )
    images._checked_get("https://art.example.com/card.png")

    assert [c["url"] for c in calls] == [
        "https://93.184.216.34/card.png",
        "https://93.184.216.34/moved.png",
    ]


def test_a_redirect_into_the_lan_is_still_refused(monkeypatch):
    answers = iter([
        [(2, 1, 6, "", ("93.184.216.34", 0))],
        [(2, 1, 6, "", ("169.254.169.254", 0))],
    ])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: next(answers))
    fake_client(monkeypatch,
                lambda i: reply(True, "http://metadata.example.com/latest/"))
    with pytest.raises(HTTPException) as e:
        images._checked_get("https://art.example.com/card.png")
    assert e.value.status_code == 400
