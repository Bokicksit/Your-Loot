"""Signing in, and everything that surrounds it."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    OWNER_ID,
    current_user,
    hash_password,
    multi_user,
    needs_setup,
    new_token,
    owner_locked,
    require_admin,
    verify_password,
)
from app.db import get_db
from app.models import ApiToken, User
from app.ratelimit import client_key, logins

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserOut(BaseModel):
    id: int
    email: str | None = None
    display_name: str | None = None
    is_admin: bool = False

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    """What the app needs before it can draw anything.

    `multi_user` tells the client whether a login screen exists at all, and
    `needs_setup` whether the very first password is still unclaimed — which
    is the difference between showing a sign-in form and showing a create-
    your-account one.
    """

    multi_user: bool
    needs_setup: bool = False
    # single-user, but the owner has set a password: show a password-only form
    locked: bool = False
    user: UserOut | None = None


# On a single-user install the email is implied — there is one account — so
# the form is just a password, or a PIN. Four digits is weak on its own and
# perfectly reasonable behind a five-tries-then-wait brake on a home network,
# which is the same bargain Plex makes.
MIN_SECRET = 4


class Credentials(BaseModel):
    email: EmailStr | None = None
    password: str = Field(min_length=MIN_SECRET, max_length=200)


class SetupIn(BaseModel):
    """Claiming an account when accounts are on. A real password, not a PIN —
    the PIN bargain only holds for one account on a home network."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=50)


class PasswordChange(BaseModel):
    current_password: str | None = None
    # None clears it: on a single-user install that takes the lock off the
    # door again, which has to be as easy as putting it on
    new_password: str | None = Field(default=None, min_length=MIN_SECRET, max_length=200)


class InviteIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=50)
    is_admin: bool = False


@router.get("/me", response_model=MeOut)
def me(request: Request, db: Session = Depends(get_db)):
    """Deliberately not a 401 when signed out — the client asks this first to
    find out which screen to draw, and an error is not an answer to that."""
    if not multi_user():
        locked = owner_locked(db)
        signed_in = not locked or request.session.get("uid") == OWNER_ID
        owner = db.get(User, OWNER_ID)
        return MeOut(
            multi_user=False,
            locked=locked,
            user=UserOut.model_validate(owner) if signed_in and owner else None,
        )
    if needs_setup(db):
        return MeOut(multi_user=True, needs_setup=True)
    uid = request.session.get("uid")
    user = db.get(User, uid) if uid else None
    return MeOut(multi_user=True, user=UserOut.model_validate(user) if user else None)


@router.post("/setup", response_model=UserOut)
def setup(body: SetupIn, request: Request, db: Session = Depends(get_db)):
    """Claim the owner account, once.

    Flipping AUTH_MODE to multi leaves an install whose owner has no password
    and therefore no way in. This is the door for exactly that moment: it
    closes for good as soon as any account has a password.
    """
    if not multi_user():
        raise HTTPException(400, "This install is in single-user mode")
    if not needs_setup(db):
        raise HTTPException(409, "Already set up — sign in instead")

    owner = db.get(User, 1)
    if owner is None:
        owner = User(id=1, is_admin=True)
        db.add(owner)
    owner.email = body.email
    owner.password_hash = hash_password(body.password)
    owner.is_admin = True
    if body.display_name:
        owner.display_name = body.display_name
    db.commit()
    db.refresh(owner)
    request.session["uid"] = owner.id
    return owner


@router.post("/login", response_model=UserOut)
def login(body: Credentials, request: Request, db: Session = Depends(get_db)):
    key = client_key(request, body.email or "owner")
    wait = logins.retry_after(key)
    if wait:
        raise HTTPException(
            429,
            f"Too many attempts. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )

    if multi_user():
        user = db.query(User).filter(User.email == body.email).one_or_none()
        wrong = "Wrong email or password"
    else:
        # one account, so the address is implied and the form asks for less
        user = db.get(User, OWNER_ID)
        wrong = "Wrong password"
        if user is not None and not user.password_hash:
            raise HTTPException(400, "This install has no password set")

    # one message for both halves: saying which was wrong tells an attacker
    # which addresses have accounts
    if user is None or not verify_password(body.password, user.password_hash):
        logins.failed(key)
        raise HTTPException(401, wrong)

    logins.succeeded(key)
    request.session["uid"] = user.id
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.post("/password", status_code=204)
def change_password(
    body: PasswordChange,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Setting the first password needs no current one — there isn't one. After
    that it always does, so a borrowed session can't lock the owner out."""
    if user.password_hash and not verify_password(body.current_password or "", user.password_hash):
        raise HTTPException(403, "Current password is wrong")
    if body.new_password is None and multi_user():
        raise HTTPException(400, "An account needs a password when accounts are on")
    user.password_hash = hash_password(body.new_password) if body.new_password else None
    db.commit()


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=201)
def invite(body: InviteIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Admin-created accounts rather than open signup. This is somebody's home
    server; a stranger finding it should not be able to make themselves one."""
    if db.query(User).filter(User.email == body.email).count():
        raise HTTPException(409, "That email already has an account")
    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(400, "You can't delete your own account")
    if user_id == 1:
        raise HTTPException(400, "The owner account can't be deleted")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "No such user")
    # their copies, wanted list, binder and settings go with them — every one
    # of those tables cascades on user_id
    db.delete(user)
    db.commit()


# --- Bearer tokens ---------------------------------------------------------
# For clients that cannot hold a cookie: a phone app, a script, another
# machine. The web UI keeps its session and never touches these.


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.get("/tokens")
def list_tokens(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Your own tokens. The values are not here and cannot be — only their
    first few characters, which is enough to tell two of them apart."""
    rows = db.scalars(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id.desc())
    ).all()
    return {
        "tokens": [
            {
                "id": t.id,
                "name": t.name,
                "prefix": t.prefix,
                "created_at": t.created_at,
                "last_used_at": t.last_used_at,
                "revoked_at": t.revoked_at,
            }
            for t in rows
        ]
    }


@router.post("/tokens", status_code=201)
def create_token(
    body: TokenCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Mint one. The reply carries the only copy of the value that will ever
    exist — it is hashed on the way in, so nothing here can show it again."""
    raw, digest, prefix = new_token()
    row = ApiToken(
        user_id=user.id, name=body.name.strip(), token_hash=digest, prefix=prefix
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "prefix": row.prefix, "token": raw}


@router.delete("/tokens/{token_id}", status_code=204)
def revoke_token(
    token_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Withdraw it. The row stays, timestamped: that this token worked until
    Tuesday and was then withdrawn is worth being able to see."""
    row = db.get(ApiToken, token_id)
    # somebody else's token is not yours to revoke, and "not found" says less
    # about their account than "not yours" would
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "token not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
