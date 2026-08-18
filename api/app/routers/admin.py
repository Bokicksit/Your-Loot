"""What the person running this needs to see and do.

Only reachable by an admin, and only worth anything on an install with more
than one account — on a single-user server the answer to every question here
is "you".

Deliberately small. This is not analytics: there is no per-person activity,
no last-seen, no counting how often somebody opens the app. What the operator
legitimately needs is how many people are here, how many have paid, whether
the catalogue is healthy and how much disk the photographs are using — and
knowing more than that about people who trusted you with their collection is
not a feature, it is a temptation.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import OWNER_ID, require_admin
from app.barcodes import stats as barcode_stats
from app.config import settings
from app.db import get_db
from app import screennames
from app.models import CollectionItem, Owned, ScreenName, User, Wanted
from app.modules import available
from app.plans import FREE, SUPPORTER, paid_modules, subscribed

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _disk_bytes(where: str) -> int:
    """How much the uploaded photographs are using.

    Walked rather than tracked in a column: the number is wanted once, on a
    page somebody opens occasionally, and a counter maintained on every
    upload and delete is a thing that drifts and then lies.
    """
    root = Path(where)
    if not root.exists():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


class AdminUser(BaseModel):
    id: int
    email: str | None = None
    # The name their public profile answers to, if they have claimed one. Here
    # because it is the one thing about an account that strangers can see, so
    # it is the one thing that occasionally has to be taken away.
    screen_name: str | None = None
    display_name: str | None = None
    is_admin: bool = False
    plan: str = FREE
    plan_until: datetime | None = None
    email_verified_at: datetime | None = None
    created_at: datetime | None = None
    subscribed: bool = False
    items: int = 0


class PlanChange(BaseModel):
    plan: str = Field(pattern=f"^({FREE}|{SUPPORTER})$")
    # None on a supporter means it does not expire — a plan granted by hand,
    # or a thank-you that should not quietly stop working.
    until: datetime | None = None


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    now = datetime.now(UTC).replace(tzinfo=None)
    users = db.scalars(select(User)).all()

    def since(days: int) -> int:
        cutoff = now - timedelta(days=days)
        return sum(1 for u in users if u.created_at and u.created_at >= cutoff)

    paying = [u for u in users if subscribed(u) and not u.is_admin]

    by_module = dict(
        db.execute(
            select(CollectionItem.module, func.count())
            .group_by(CollectionItem.module)
        ).all()
    )
    owned_by_module = dict(
        db.execute(
            select(CollectionItem.module, func.count())
            .join(Owned, Owned.item_id == CollectionItem.id)
            .group_by(CollectionItem.module)
        ).all()
    )

    return {
        "accounts": {
            "total": len(users),
            "verified": sum(1 for u in users if u.email_verified_at),
            "subscribers": len(paying),
            "admins": sum(1 for u in users if u.is_admin),
            "new_7d": since(7),
            "new_30d": since(30),
        },
        # gross, before Stripe's cut — the plan document has the real net
        "revenue": {"monthly_gross_usd": round(len(paying) * 4.0, 2)},
        "catalogue": {
            "items": sum(by_module.values()),
            "by_module": {m: by_module.get(m, 0) for m in available()},
        },
        "collections": {
            "copies": db.scalar(select(func.count()).select_from(Owned)) or 0,
            "wanted": db.scalar(select(func.count()).select_from(Wanted)) or 0,
            "owned_by_module": {m: owned_by_module.get(m, 0) for m in available()},
        },
        "storage": {"photos_bytes": _disk_bytes(settings.image_dir)},
        "barcodes": barcode_stats(db),
        "install": {
            "available_modules": available(),
            "paid_modules": paid_modules(),
            "open_signup": settings.open_signup,
        },
    }


@router.get("/users", response_model=list[AdminUser])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    counts = dict(
        db.execute(
            select(Owned.user_id, func.count()).group_by(Owned.user_id)
        ).all()
    )
    rows = db.scalars(select(User).order_by(User.id)).all()
    # Every live name in one query rather than one per row.
    names = dict(
        db.execute(
            select(ScreenName.user_id, ScreenName.display).where(
                ScreenName.revoked.is_(False)
            )
        ).all()
    )
    return [
        AdminUser(
            id=u.id,
            screen_name=names.get(u.id),
            email=u.email,
            display_name=u.display_name,
            is_admin=u.is_admin,
            plan=u.plan or FREE,
            plan_until=u.plan_until,
            email_verified_at=u.email_verified_at,
            created_at=u.created_at,
            subscribed=subscribed(u),
            items=counts.get(u.id, 0),
        )
        for u in rows
    ]


@router.put("/users/{user_id}/plan", response_model=AdminUser)
def set_plan(
    user_id: int,
    body: PlanChange,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Grant or withdraw a plan by hand.

    The way plans are set until Stripe exists, and the way they are fixed
    afterwards when a payment goes strange — somebody who has paid and cannot
    get in should not have to wait for a webhook to be debugged.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "No such user")
    if user.id == OWNER_ID and body.plan == FREE:
        # harmless, since admins bypass the paywall anyway, but it reads as a
        # mistake and saying so costs nothing
        raise HTTPException(400, "The owner is an admin and is never billed")

    user.plan = body.plan
    user.plan_until = body.until if body.plan == SUPPORTER else None
    db.commit()
    db.refresh(user)
    return AdminUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        plan=user.plan,
        plan_until=user.plan_until,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        subscribed=subscribed(user),
        items=db.scalar(
            select(func.count()).select_from(Owned).where(Owned.user_id == user.id)
        ) or 0,
    )


@router.delete("/users/{user_id}/screen-name", status_code=204)
def revoke_screen_name(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Take somebody's screen name away, permanently.

    The only lever there is, and deliberately the only one: an administrator
    can remove a name but cannot choose a replacement. Picking names for
    people would make you responsible for the next one, and there is no
    version of that which ends well.

    What happens: the name is spent — nobody can claim it again, including
    them — their profile stops answering, and they may claim one different
    name. Their collection is untouched, because this is about a word in a
    URL and nothing else.

    This exists because the word list in screennames.py catches the obvious
    and nothing more. It was never going to be the whole answer, and pretending
    otherwise in the terms would be the mistake.
    """
    row = db.scalar(
        select(ScreenName).where(
            ScreenName.user_id == user_id, ScreenName.revoked.is_(False)
        )
    )
    if row is None:
        raise HTTPException(404, "that account has no screen name")
    screennames.revoke(db, row.name)
    db.commit()
