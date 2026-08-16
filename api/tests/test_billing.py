"""Can somebody give themselves a paid plan?

The webhook is a public URL whose whole job is granting subscriptions. If its
signature check is wrong, the paywall is decorative — anyone who can read the
docs can POST themselves a plan. So most of this file is that one function,
attacked from every direction it can be attacked from.

Stripe itself is never called. What is worth testing here is what this server
believes and what it refuses to believe, and a suite that needed live API
keys would simply not run.

    docker compose -f compose.test.yaml run --rm tests
"""

import hashlib
import hmac
import json
import os
import time

import httpx
import pytest

from app import billing
from app.billing import TOLERANCE_SECONDS, verify_signature

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
SECRET = "whsec_test_only_not_a_real_secret"


def sign(payload: bytes, secret: str = SECRET, stamp: int | None = None) -> str:
    stamp = stamp if stamp is not None else int(time.time())
    mac = hmac.new(secret.encode(), b"%d." % stamp + payload, hashlib.sha256)
    return f"t={stamp},v1={mac.hexdigest()}"


BODY = json.dumps({"type": "checkout.session.completed"}).encode()


# --- the lock on the door --------------------------------------------------


def test_a_real_signature_passes():
    assert verify_signature(BODY, sign(BODY), SECRET) is True


def test_an_invented_signature_fails():
    forged = f"t={int(time.time())},v1={'a' * 64}"
    assert verify_signature(BODY, forged, SECRET) is False


def test_a_body_changed_after_signing_fails():
    """The attack this exists to stop: a real captured event with the amount
    or the customer swapped."""
    header = sign(BODY)
    tampered = BODY.replace(b"completed", b"COMPLETED")
    assert verify_signature(tampered, header, SECRET) is False


def test_the_wrong_secret_fails():
    assert verify_signature(BODY, sign(BODY, "whsec_someone_elses"), SECRET) is False


def test_an_old_request_fails():
    """Replay protection. Without it a request captured once works forever."""
    stale = int(time.time()) - TOLERANCE_SECONDS - 30
    assert verify_signature(BODY, sign(BODY, stamp=stale), SECRET) is False


def test_a_request_from_the_future_fails():
    ahead = int(time.time()) + TOLERANCE_SECONDS + 30
    assert verify_signature(BODY, sign(BODY, stamp=ahead), SECRET) is False


def test_a_recent_request_inside_the_window_passes():
    recent = int(time.time()) - (TOLERANCE_SECONDS - 30)
    assert verify_signature(BODY, sign(BODY, stamp=recent), SECRET) is True


@pytest.mark.parametrize("header", [
    "", "nonsense", "t=123", f"v1={'a' * 64}", "t=,v1=", "t=abc,v1=def",
])
def test_a_malformed_header_fails(header):
    assert verify_signature(BODY, header, SECRET) is False


def test_no_secret_means_no_and_never_yes():
    """Unconfigured must not read as valid. A missing secret that returned
    True would be the whole paywall gone, silently."""
    assert verify_signature(BODY, sign(BODY), "") is False
    assert verify_signature(BODY, "", "") is False


def test_more_than_one_signature_is_allowed():
    """Stripe sends several while a secret is being rotated, and any one of
    them matching is enough."""
    good = sign(BODY).split("v1=")[1]
    stamp = int(time.time())
    header = f"t={stamp},v1={'b' * 64},v1={sign(BODY, stamp=stamp).split('v1=')[1]}"
    assert good  # the helper works
    assert verify_signature(BODY, header, SECRET) is True


# --- the routes, on an install with no keys --------------------------------


def test_billing_does_not_exist_without_keys(owner):
    """Every self-hosted install, and this test stack. Not a disabled button
    somewhere — the routes are simply not there."""
    assert not billing.configured()

    for path in ("/api/billing/checkout", "/api/billing/portal", "/api/billing/webhook"):
        r = owner.post(path)
        assert r.status_code == 404, f"{path} answered {r.status_code} with no keys set"


def test_a_checkout_request_is_actually_form_encoded(monkeypatch):
    """What this sends, not what it means to send.

    The first version passed httpx a list of pairs, which httpx treats as raw
    body content rather than form fields — so the request body was the repr
    of a Python list and it died inside the HTTP layer before Stripe ever saw
    it. Every field here is checked on the wire because that failure is
    invisible until the day real keys are plugged in.
    """
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_abc")

    seen = {}

    def fake_post(url, data=None, auth=None, timeout=None, **kw):
        seen["url"] = url
        seen["data"] = data
        seen["auth"] = auth

        class R:
            def raise_for_status(self):
                pass

            @staticmethod
            def json():
                return {"url": "https://checkout.stripe.com/c/pay/test"}

        return R()

    monkeypatch.setattr(billing.httpx, "post", fake_post)

    url = billing.checkout_url(
        user_id=7, email="a@example.com", customer_id=None,
        success_url="https://x/ok", cancel_url="https://x/no",
    )
    assert url.startswith("https://checkout.stripe.com/")
    assert isinstance(seen["data"], dict), "httpx would send a non-dict as raw body"
    assert seen["data"]["line_items[0][price]"] == "price_abc"
    assert seen["data"]["client_reference_id"] == "7"
    assert seen["data"]["mode"] == "subscription"
    # no customer yet, so Stripe is told the address instead
    assert seen["data"]["customer_email"] == "a@example.com"
    assert "customer" not in seen["data"]
    assert seen["auth"] == ("sk_test_x", "")


def test_a_returning_customer_is_matched_not_duplicated(monkeypatch):
    """Somebody who already has a Stripe customer must be sent back to it,
    or they collect a second one and the webhook matches the wrong row."""
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_abc")
    seen = {}

    def fake_post(url, data=None, **kw):
        seen.update(data)

        class R:
            def raise_for_status(self): pass
            @staticmethod
            def json(): return {"url": "https://checkout.stripe.com/c/pay/test"}

        return R()

    monkeypatch.setattr(billing.httpx, "post", fake_post)
    billing.checkout_url(
        user_id=7, email="a@example.com", customer_id="cus_123",
        success_url="https://x/ok", cancel_url="https://x/no",
    )
    assert seen["customer"] == "cus_123"
    assert "customer_email" not in seen, "a known customer was sent as a new one"


def test_status_says_billing_is_unavailable(owner):
    """This one answers rather than 404s, because the settings screen asks it
    in order to decide whether to draw anything at all."""
    s = owner.get("/api/billing/status")
    assert s.status_code == 200
    assert s.json()["available"] is False


def test_the_webhook_is_refused_when_it_cannot_be_verified(monkeypatch, owner):
    """Keys set but no webhook secret. The route must vanish rather than
    accept whatever arrives — this is the failure that would hand the paywall
    to anybody who found the URL."""
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_x")
    monkeypatch.setattr(billing.settings, "stripe_webhook_secret", "")

    assert billing.configured() is True
    assert billing.webhooks_configured() is False
    assert verify_signature(BODY, sign(BODY)) is False, \
        "an unconfigured webhook secret accepted a signature"


# --- what confirming an address is actually for ----------------------------


def test_checkout_needs_a_confirmed_address(monkeypatch):
    """The one thing verification gates, and the reason it exists at all.

    Taking money from an address we cannot reach means no receipt, no
    renewal notice and nowhere to send a refund. It is also the cheapest
    possible moment to ask: anybody willing to pay will click a link.
    """
    from fastapi import HTTPException

    from app.routers.billing import start_checkout

    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_x")

    class Unconfirmed:
        id = 7
        email = "a@example.com"
        email_verified_at = None
        stripe_customer_id = None

    with pytest.raises(HTTPException) as e:
        start_checkout(user=Unconfirmed())
    assert e.value.status_code == 409
    assert "confirm" in e.value.detail.lower()


def test_a_reset_is_not_gated_on_it(owner):
    """Deliberately the other way. Somebody who mistyped their address and
    never confirmed would be locked out of their own collection for good,
    which is a far worse failure than the one gating it would prevent."""
    import inspect

    from app.routers import auth as auth_router

    source = inspect.getsource(auth_router.forgot_password)
    assert "email_verified_at" not in source,         "a password reset started requiring a confirmed address"
