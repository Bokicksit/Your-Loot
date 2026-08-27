"""A brake on guessing.

A login endpoint without one lets somebody try passwords as fast as they can
send requests, which turns any short or reused password into a matter of
minutes. That matters more here than on a big service: there is no security
team watching, no anomaly detection, and often exactly one account.

In memory rather than in the database, deliberately. Failed logins are not
worth a write, the counter resetting when the container restarts costs an
attacker a few seconds and nothing else, and a self-hosted app should not
need Redis to have a login form.
"""

import ipaddress
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.auth import current_user as _current_user
from app.config import settings


class Attempts:
    """A sliding window of failures per key.

    Only failures are counted, and a success clears the key — so somebody
    typing their own password wrong twice and then getting it right is never
    penalised, while somebody working through a list is.
    """

    def __init__(self, limit: int, window: int, ceiling: int = 4096):
        self.limit = limit
        self.window = window
        self.ceiling = ceiling  # keys, so a spray attack can't grow this forever
        self._hits: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque:
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
        return hits

    def retry_after(self, key: str) -> int:
        """Seconds until this key may try again, or 0 if it may now."""
        now = time.monotonic()
        hits = self._prune(key, now)
        if len(hits) < self.limit:
            return 0
        return max(1, int(self.window - (now - hits[0])) + 1)

    def failed(self, key: str) -> None:
        now = time.monotonic()
        if len(self._hits) > self.ceiling:
            # cheap eviction: drop whatever has already aged out
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                self._hits.pop(k, None)
        self._hits[key].append(now)

    def succeeded(self, key: str) -> None:
        self._hits.pop(key, None)

    def used(self, key: str) -> None:
        """Record a use.

        The same bookkeeping as `failed`, under the name that describes what
        the lookup brake below is counting: not wrong answers, but calls that
        each cost something. Kept as its own name so a call site reads as the
        thing it means.
        """
        self.failed(key)


# Five wrong answers, then a five-minute wait. Slow enough that a four-digit
# PIN takes weeks rather than seconds, loose enough that nobody mistyping
# their own password on a phone notices it exists.
logins = Attempts(limit=5, window=300)

# Mail costs money and lands in somebody's inbox, so the brake here is not
# about guessing — nobody is brute-forcing "send me an email". It is about
# not letting one address be used to post a hundred messages at a stranger,
# and not letting a stuck client empty the sending quota. Counted per address
# rather than per attempt, so three in an hour is generous for a person and
# useless for a mail bomb.
mails = Attempts(limit=3, window=3600)

# Signups from one address. A person makes one account; a script makes as many
# as it can until something stops it. The number is a setting because the two
# ends of it pull opposite ways: a household, an office or a school all share
# one address and might legitimately produce several in an evening, while the
# thing this is for wants thousands. Twenty stops the second without ever
# being noticed by the first.
signups = Attempts(limit=settings.signup_limit, window=3600)


# Searches that leave the building: Rebrickable, IGDB, TMDB, Discogs,
# ComicVine, OpenLibrary, upcitemdb, TCGdex. These are not guessing attacks
# and the brake is not about security — it is about a shared, finite resource.
# The API keys belong to the server, not to the person searching, so one
# account in a loop spends everybody's quota, and several of these free tiers
# are counted per day. Keyed on the account rather than the address on
# purpose: the quota is spent by whoever is signed in, and moving to another
# network should not hand them a second helping. Every one of these endpoints
# requires a login, so there is always an account to charge.
#
# A minute's worth is far past what a person types and far under what a script
# manages, which is the whole trick — nobody searching for a Lego set will
# ever see it.
lookups = Attempts(limit=settings.lookup_limit, window=60)


def client_address(request) -> str:
    """The address at the far end, as far as it can honestly be known.

    X-Forwarded-For is a list anybody can start. A caller sets it to whatever
    they like and each proxy appends the address it actually saw, so the
    entries arrive oldest-first and only the tail — the part the proxies wrote
    — means anything. Reading the head, which is what this used to do, is
    reading the attacker's own text: a different value per request is a fresh
    bucket per request, and the login, signup and mail brakes stop existing.

    So count in from the right by however many proxies are really there
    (`trusted_proxies`), and fall back to the socket's own address whenever
    the header is shorter than it should be or holds something that is not an
    address — both meaning it was not written by the proxies it claims.
    """
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxies
    if hops <= 0:
        return peer  # nothing in front, so nothing may rewrite the address

    chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
    chain = [p for p in chain if p]
    if len(chain) < hops:
        return peer
    candidate = chain[-hops]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer  # not an address; a proxy would not have written it
    return candidate


def client_key(request, identifier: str | None = None) -> str:
    """Who is doing the guessing.

    Keyed on address *and* account, so one person failing to sign in cannot
    lock anybody else out, and somebody working through a list of accounts
    from one address is still stopped.
    """
    return f"{client_address(request)}|{(identifier or '').strip().lower()}"


def outbound(user=Depends(_current_user)) -> None:
    """Charge this request against the account's third-party search budget.

    A dependency rather than a line in each handler so that adding a route
    that calls somebody else's API is a one-word decision, and so that the
    count happens before the handler — a call refused here never reaches the
    provider, which is the entire point.
    """
    key = f"user:{user.id}"
    wait = lookups.retry_after(key)
    if wait:
        raise HTTPException(
            429,
            f"Too many searches. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    lookups.used(key)
