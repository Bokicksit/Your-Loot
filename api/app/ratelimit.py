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

import time
from collections import defaultdict, deque


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


# Five wrong answers, then a five-minute wait. Slow enough that a four-digit
# PIN takes weeks rather than seconds, loose enough that nobody mistyping
# their own password on a phone notices it exists.
logins = Attempts(limit=5, window=300)


def client_key(request, identifier: str | None = None) -> str:
    """Who is doing the guessing.

    Keyed on address *and* account, so one person failing to sign in cannot
    lock anybody else out, and somebody working through a list of accounts
    from one address is still stopped.

    nginx sits in front and is the only thing that reaches the API — the
    compose files never publish its port — so the forwarded address is as
    trustworthy as anything here gets.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    addr = forwarded.split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    return f"{addr}|{(identifier or '').strip().lower()}"
