"""Who has paid, and what that buys.

Three rules, and the first two matter more than the third.

**Nothing is paid unless this install says so.** PAID_MODULES is empty
everywhere except the hosted service, so a self-hosted install has no tiers,
no locked collections and no upsell — the person running it already paid, by
running it.

**Leaving is never behind the paywall.** Backup and export are open to
everybody, always, including somebody whose subscription lapsed yesterday.
A collection you cannot get out of is a hostage, and the whole promise of
this app is that yours isn't.

**Lapsing hides, it never deletes.** A plan that runs out closes the door on
a collection; it does not touch a row of it. Pay again and everything is
where you left it, because it never went anywhere.
"""

from datetime import UTC, datetime

from app.config import settings
from app.models import User

FREE = "free"
SUPPORTER = "supporter"


def paid_modules() -> list[str]:
    """Collections this install charges for. Empty is the normal case."""
    return [m.strip().lower() for m in settings.paid_modules.split(",") if m.strip()]


def costs_money(module: str) -> bool:
    return module in paid_modules()


def subscribed(user: User) -> bool:
    """Is this account's plan good right now?

    Admins are not billed. Somebody has to be able to look at the thing they
    are running, and an owner locked out of their own service by a payment
    system they have not built yet is a silly way to start.
    """
    if user is None:
        return False
    if user.is_admin:
        return True
    if (user.plan or FREE) != SUPPORTER:
        return False
    # No end date means it does not end — which is what a plan set by hand
    # means, and what a lifetime one would mean later.
    if user.plan_until is None:
        return True
    return user.plan_until > datetime.now(UTC).replace(tzinfo=None)


def sells_anything() -> bool:
    """Does this install charge for anything at all?

    False on every self-hosted one — no paid collections and no limits set —
    and that is the answer to "is there a tier here", which is a different
    question from "has this person paid".
    """
    from app import limits  # imports plans, so not at module scope

    return bool(paid_modules()) or any(
        (limits.card_limit(), limits.dex_limit(), limits.binder_limit())
    )


def themed(user: User) -> bool:
    """Does this account's public profile get the room?

    Where nothing is sold there is no tier to be outside of, so everybody in
    the house gets it — the same reasoning as limits.limited(). Where the
    service does sell something, the room is what a Supporter bought.
    """
    return not sells_anything() or subscribed(user)


def may_open(user: User, module: str) -> bool:
    return not costs_money(module) or subscribed(user)
