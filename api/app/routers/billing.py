"""Starting a subscription, managing it, and hearing back about it.

Three routes, and they are not equally dangerous. The first two are behind a
session and can only affect the person calling them. The webhook is a public
URL that hands out paid plans, so everything about it is written on the
assumption that whoever is calling is not Stripe until proven otherwise.

Rules the webhook follows, each because the alternative is a real failure:

* **Unverified is refused.** A webhook secret that is not set means the route
  does not exist, rather than the signature check being skipped.
* **Cancelling does not lock somebody out today.** They paid to the end of
  the period, so the plan is left to expire on its own date.
* **Unknown events are accepted and ignored.** Stripe sends far more than
  this cares about, and answering anything but 200 makes it retry forever.
* **Everything is idempotent.** Stripe delivers at least once, and a
  duplicate must not double anything.
"""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.billing import (
    checkout_url,
    configured,
    portal_url,
    verify_signature,
    webhooks_configured,
)
from app.config import settings
from app.db import get_db
from app.models import User
from app.plans import FREE, SUPPORTER

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _needs_stripe():
    if not configured():
        raise HTTPException(404, "Not found")


def _site() -> str:
    return (settings.public_url or "").rstrip("/")


@router.get("/status")
def status(user: User = Depends(current_user)):
    """What the settings screen needs to decide which button to draw."""
    return {
        "available": configured(),
        "plan": user.plan or FREE,
        "plan_until": user.plan_until,
        # only somebody Stripe already knows can be sent to the portal
        "can_manage": bool(configured() and user.stripe_customer_id),
        # so the screen can ask for the address up front rather than letting
        # somebody press a button that is going to refuse them
        "needs_confirmed_email": user.email_verified_at is None,
    }


@router.post("/checkout")
def start_checkout(user: User = Depends(current_user)):
    _needs_stripe()
    # The one thing confirming an address is for. Taking money from somebody
    # we cannot send a receipt, a renewal notice or a refund to is a bad
    # bargain for both of us, and this is the moment where the cost of asking
    # is lowest — anybody willing to pay will click a link.
    #
    # Not applied to the password reset, deliberately: somebody who mistyped
    # their address and never confirmed would be locked out of their own
    # collection for good, which is a far worse failure than this prevents.
    if user.email_verified_at is None:
        raise HTTPException(
            409, "Confirm your email address first — we'll need it to send you a receipt."
        )
    try:
        url = checkout_url(
            user_id=user.id,
            email=user.email,
            customer_id=user.stripe_customer_id,
            success_url=f"{_site()}/settings?paid=1",
            cancel_url=f"{_site()}/settings",
        )
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not reach the payment page: {e}")
    return {"url": url}


@router.post("/portal")
def manage_subscription(user: User = Depends(current_user)):
    """Stripe's own page, where cancelling lives.

    Deliberately not a cancel button of our own: somebody who wants to stop
    paying should not have to go through the people being paid.
    """
    _needs_stripe()
    if not user.stripe_customer_id:
        raise HTTPException(400, "There is no subscription on this account")
    try:
        url = portal_url(user.stripe_customer_id, return_url=f"{_site()}/settings")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not reach the billing portal: {e}")
    return {"url": url}


# --- the public one --------------------------------------------------------


def _period_end(obj: dict) -> datetime | None:
    ts = obj.get("current_period_end")
    return datetime.fromtimestamp(ts, UTC).replace(tzinfo=None) if ts else None


def _find_user(db: Session, *, user_id=None, customer=None) -> User | None:
    """Whose account this event is about.

    By our own id when the event carries one — the first checkout does — and
    by the stored Stripe customer afterwards, since renewals and
    cancellations know nothing about us.
    """
    if user_id:
        try:
            found = db.get(User, int(user_id))
        except (TypeError, ValueError):
            found = None
        if found:
            return found
    if customer:
        return db.scalar(select(User).where(User.stripe_customer_id == customer))
    return None


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    if not configured() or not webhooks_configured():
        raise HTTPException(404, "Not found")

    raw = await request.body()
    if not verify_signature(raw, request.headers.get("stripe-signature", "")):
        # No detail on purpose: telling a forger which part was wrong is help.
        raise HTTPException(400, "Bad signature")

    event = await request.json()
    kind = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if kind == "checkout.session.completed":
        user = _find_user(
            db, user_id=obj.get("client_reference_id"), customer=obj.get("customer")
        )
        if user:
            # Remember the customer before anything else: without it no later
            # event about this person can be matched to them at all.
            if obj.get("customer"):
                user.stripe_customer_id = obj["customer"]
            user.plan = SUPPORTER
            db.commit()

    elif kind in ("customer.subscription.created", "customer.subscription.updated"):
        user = _find_user(
            db,
            user_id=(obj.get("metadata") or {}).get("user_id"),
            customer=obj.get("customer"),
        )
        if user:
            state = obj.get("status")
            if state in ("active", "trialing"):
                user.plan = SUPPORTER
                user.plan_until = _period_end(obj)
            elif state in ("past_due", "unpaid"):
                # A card that failed is not a decision to leave. Stripe
                # retries for days; the plan runs to the date already paid
                # for and lapses on its own if nothing arrives.
                user.plan_until = _period_end(obj) or user.plan_until
            else:
                user.plan = FREE
                user.plan_until = None
            db.commit()

    elif kind == "customer.subscription.deleted":
        user = _find_user(
            db,
            user_id=(obj.get("metadata") or {}).get("user_id"),
            customer=obj.get("customer"),
        )
        if user:
            # Cancelled, but paid up to a date — so leave the date rather
            # than shutting the door on somebody the same afternoon they
            # cancelled. It expires by itself.
            end = _period_end(obj)
            if end and end > datetime.now(UTC).replace(tzinfo=None):
                user.plan_until = end
            else:
                user.plan = FREE
                user.plan_until = None
            db.commit()

    # Everything else: Stripe sends a great deal this does not care about,
    # and anything but a 200 makes it retry until it gives up.
    return {"received": True}
