"""Taking money, and — more importantly — not being told lies about it.

Talks to Stripe over plain HTTP rather than through their library. Two
endpoints are needed and the whole surface is form-encoded POSTs, which is
not worth adding a dependency to every self-hosted image for, when no
self-hosted install will ever call any of it.

The part that actually matters is `verify_signature`. The webhook is a public
URL that grants paid plans, so an unverified one is a form anybody on the
internet can fill in to give themselves a subscription. Everything else here
is plumbing; that function is the lock on the door, which is why it is
written to be tested rather than trusted.
"""

import hashlib
import hmac
import time

import httpx

from app.config import settings

API = "https://api.stripe.com/v1"

# Stripe signs "<timestamp>.<raw body>". Five minutes is their own suggested
# tolerance: long enough for a slow retry, short enough that a captured
# request cannot be replayed tomorrow.
TOLERANCE_SECONDS = 300


def configured() -> bool:
    """Whether this install can take payments at all.

    Every route in the billing router 404s when this is false, which is every
    self-hosted install and this one until the keys are set.
    """
    return bool(settings.stripe_secret_key and settings.stripe_price_id)


def webhooks_configured() -> bool:
    return bool(settings.stripe_webhook_secret)


def _parse_header(header: str) -> tuple[int | None, list[str]]:
    """`t=1614556800,v1=abc,v1=def` -> (1614556800, [abc, def]).

    More than one v1 is normal while a signing secret is being rotated, so
    they are all returned and any one of them may match.
    """
    stamp: int | None = None
    signatures: list[str] = []
    for part in (header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            stamp = int(value)
        elif key == "v1" and value:
            signatures.append(value)
    return stamp, signatures


def verify_signature(
    payload: bytes,
    header: str,
    secret: str | None = None,
    now: float | None = None,
) -> bool:
    """Did Stripe really send this?

    False for anything doubtful, and deliberately not an exception with a
    reason in it — the caller answers 400 either way, and telling a forger
    which part of their forgery was wrong is free help.
    """
    secret = secret if secret is not None else settings.stripe_webhook_secret
    if not secret:
        return False  # unconfigured is not the same as valid

    stamp, signatures = _parse_header(header)
    if stamp is None or not signatures:
        return False

    # Replay protection. Without this a request captured once works forever.
    if abs((now if now is not None else time.time()) - stamp) > TOLERANCE_SECONDS:
        return False

    signed = b"%d." % stamp + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    # compare_digest, not ==: a plain comparison returns early on the first
    # wrong byte and leaks the answer a byte at a time to anyone timing it.
    return any(hmac.compare_digest(expected, s) for s in signatures)


def _post(path: str, data: dict[str, str]) -> dict:
    """Form-encoded, which is the only thing Stripe's API accepts.

    A dict and not a list of pairs: httpx treats a non-dict `data` as raw
    body content, so a list of tuples is sent as the literal repr of a list
    and the request dies inside the HTTP layer rather than at Stripe. Every
    key Stripe wants here is unique — the nesting is in the names, as in
    `line_items[0][price]` — so a dict loses nothing.
    """
    resp = httpx.post(
        f"{API}{path}",
        data=data,
        auth=(settings.stripe_secret_key, ""),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def checkout_url(user_id: int, email: str | None, customer_id: str | None,
                 success_url: str, cancel_url: str) -> str:
    """A hosted page to pay on.

    `client_reference_id` carries our own user id there and back, which is how
    the first webhook knows whose account was just paid for — before that
    moment there is no Stripe customer on the row to match against.
    """
    data = {
        "mode": "subscription",
        "line_items[0][price]": settings.stripe_price_id,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(user_id),
        "success_url": success_url,
        "cancel_url": cancel_url,
        # carried onto the subscription, so renewals and cancellations months
        # later still say whose they are
        "subscription_data[metadata][user_id]": str(user_id),
    }
    if customer_id:
        data["customer"] = customer_id
    elif email:
        data["customer_email"] = email
    return _post("/checkout/sessions", data)["url"]


def portal_url(customer_id: str, return_url: str) -> str:
    """Stripe's own page for changing a card or cancelling.

    Cancelling has to be somewhere a person can reach without asking us,
    which is both decent and what the app stores expect.
    """
    return _post(
        "/billing_portal/sessions",
        {"customer": customer_id, "return_url": return_url},
    )["url"]
