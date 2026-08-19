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
from app.models import CollectionItem, Owned, ScreenName, Setting, User, Wanted
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
    # Whether that name actually answers. A name is claimed at sign-up and a
    # profile is published later, or never — so most accounts have one and no
    # page behind it, and a panel that linked every name would offer a row of
    # links that all say "no such profile".
    profile_public: bool = False
    display_name: str | None = None
    is_admin: bool = False
    # Given the tier rather than charged for it. Kept out of the subscriber
    # count and out of the revenue line; everything else about them is the
    # same as anybody else on it.
    comped: bool = False
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

    # Who is actually paying. An admin is never billed and a comped account
    # was never charged, so neither is revenue — and a subscriber count that
    # included them would be wrong by the same amount every month, in the
    # same direction, which is the kind of wrong nobody notices.
    paying = [u for u in users if subscribed(u) and not u.is_admin and not u.comped]
    given = [u for u in users if subscribed(u) and not u.is_admin and u.comped]

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
            # Said separately rather than folded in or left out — they are
            # real accounts on the real tier, and the operator chose that.
            "comped": len(given),
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
    # Who has actually published something, asked the way the profile page
    # asks it — one query for everybody rather than one per row.
    from app.routers.profile import PUBLIC_KEY, shown_scopes

    published = {
        r.user_id: shown_scopes(r.value)
        for r in db.scalars(
            select(Setting).where(Setting.key == PUBLIC_KEY)
        ).all()
    }
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
            profile_public=bool(names.get(u.id) and published.get(u.id)),
            email=u.email,
            display_name=u.display_name,
            is_admin=u.is_admin,
            comped=u.comped,
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
        comped=user.comped,
        plan=user.plan,
        plan_until=user.plan_until,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        subscribed=subscribed(user),
        items=db.scalar(
            select(func.count()).select_from(Owned).where(Owned.user_id == user.id)
        ) or 0,
    )


class CompedChange(BaseModel):
    comped: bool


@router.put("/users/{user_id}/comped", response_model=AdminUser)
def set_comped(
    user_id: int,
    body: CompedChange,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Mark an account as given the tier rather than charged for it.

    Changes nothing about what they can open — a comped supporter is a
    supporter. It changes one number: how many subscribers this install has,
    which is a question about the business and should not be answered with
    the people you gave it to.

    Separate from the plan itself on purpose. Somebody can be comped before
    the plan is granted or after it lapses, and the flag surviving that is
    what makes it a fact about the person rather than about the plan.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "No such user")
    if user.is_admin:
        # already outside the count, and a second reason to be outside it
        # would only be a second thing to keep true
        raise HTTPException(400, "An admin is never billed and never counted")

    user.comped = bool(body.comped)
    db.commit()
    db.refresh(user)
    return AdminUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        comped=user.comped,
        plan=user.plan or FREE,
        plan_until=user.plan_until,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        subscribed=subscribed(user),
        items=db.scalar(
            select(func.count()).select_from(Owned).where(Owned.user_id == user.id)
        ) or 0,
    )


@router.post("/repair-covers")
def repair_covers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Heal record covers that were stored as dead links.

    MusicBrainz results guess their Cover Art Archive URL, and for a while a
    guess that turned out wrong was stored anyway — so a shelf of records
    rendered as broken frames. This walks every record whose picture still
    points at the archive and settles each one: an image that answers is
    copied into our own storage, where it cannot break again; one the archive
    says it does not have is cleared, so the tile shows the honest
    placeholder and its owner can add a photo or re-pick the pressing.

    Idempotent — after one pass nothing points at the archive any more —
    and per-row: a failure on one record leaves the rest repaired.
    """
    import uuid as uuidlib
    from pathlib import Path as FsPath

    import httpx as _httpx

    from app.config import settings as cfg
    from app.routers.images import EXT_BY_TYPE, MAX_BYTES, _checked_get
    from app.trim import trim_border

    # Two ways a stored picture lies. A guessed archive URL that never
    # existed — the original bug — and a local file that has since vanished,
    # which is what a server without a persistent volume does to everything
    # on its disk at every deploy. Both end the same way for the person
    # looking: a broken frame where their cover was.
    missing = 0
    local = db.scalars(
        select(CollectionItem).where(CollectionItem.image_url.like("/images/%"))
    ).all()
    root = FsPath(cfg.image_dir)
    for item in local:
        name = item.image_url.split("/")[-1].split("?")[0]
        if name and not (root / name).is_file():
            item.image_url = None
            missing += 1
    if missing:
        db.commit()

    rows = db.scalars(
        select(CollectionItem).where(
            CollectionItem.module == "records",
            CollectionItem.image_url.like("https://coverartarchive.org/%"),
        )
    ).all()

    copied, cleared, kept = 0, 0, 0
    for item in rows:
        try:
            resp = _checked_get(item.image_url)
        except _httpx.HTTPError:
            kept += 1  # unreachable is not the same as gone; try again later
            continue
        if resp.status_code in (404, 410):
            item.image_url = None
            cleared += 1
            db.commit()
            continue
        ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        ext = EXT_BY_TYPE.get(ctype)
        if resp.status_code != 200 or not ext or len(resp.content) > MAX_BYTES:
            kept += 1
            continue
        name = f"{uuidlib.uuid4().hex}{ext}"
        (FsPath(cfg.image_dir) / name).write_bytes(trim_border(resp.content))
        item.image_url = f"/images/{name}"
        copied += 1
        db.commit()

    return {
        "checked": len(rows) + len(local),
        "copied": copied,
        "cleared": cleared,
        "missing_files": missing,
        "kept": kept,
    }


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
