"""Who may look at an uploaded photograph.

These are pictures of somebody's own things — the shelf, the sleeve, the
graded slab with their name on the label. They were served to anybody who
knew the URL, forever. Filenames are random hex so nothing could be
enumerated, but that is obscurity rather than access control, and on a
public service the difference matters.

Two ways in, because one is not enough:

* **A session.** What the app itself uses. A browser sends the cookie with
  every `<img>` request on the same origin, so nothing anywhere had to start
  rewriting URLs — and a rewrite missed in one of fifteen serialisers is
  exactly the kind of bug that hides.
* **A signature.** For clients that hold a bearer token instead of a cookie,
  because an `<img>` tag cannot send an Authorization header. Short-lived and
  tied to the one filename, so a link that leaks stops working.

Neither says *whose* photograph it is. That would need the file to be
attributed to an account, which uploads have never recorded — worth doing,
and a bigger change than this. What this fixes is the open door.
"""

import hashlib
import hmac
import time

from app.auth import session_secret

# An hour. Long enough that a page open on a slow connection keeps working,
# short enough that a URL copied out of a network log is stale by the time
# anybody reads it.
DEFAULT_TTL = 3600


def sign(name: str, ttl: int = DEFAULT_TTL, now: float | None = None) -> str:
    """A token for one filename, good for a while. `<expiry>.<mac>`."""
    expires = int((now if now is not None else time.time()) + ttl)
    return f"{expires}.{_mac(name, expires)}"


def verify(name: str, token: str | None, now: float | None = None) -> bool:
    """False for anything at all doubtful — expired, altered, malformed, or
    signed for a different file."""
    if not token:
        return False
    expiry, _, mac = token.partition(".")
    if not expiry.isdigit() or not mac:
        return False
    if int(expiry) < (now if now is not None else time.time()):
        return False
    # constant time: a plain == leaks the right answer a byte at a time to
    # anybody willing to measure how long the wrong one took
    return hmac.compare_digest(_mac(name, int(expiry)), mac)


def _mac(name: str, expires: int) -> str:
    """The filename is inside the signature, so a token minted for one photo
    cannot be used to fetch another."""
    return hmac.new(
        session_secret().encode(), f"{name}:{expires}".encode(), hashlib.sha256
    ).hexdigest()[:32]
