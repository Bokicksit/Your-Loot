"""Signing in, and everything that surrounds it."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    OWNER_ID,
    RESET_MINUTES,
    VERIFY_HOURS,
    current_user,
    hash_password,
    issue_link_token,
    multi_user,
    needs_setup,
    new_token,
    owner_locked,
    require_admin,
    spend_link_token,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.mailer import send_reset, send_verification
from app.models import ApiToken, AuthToken, User
from app.ratelimit import client_key, logins, mails, signups

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserOut(BaseModel):
    id: int
    email: str | None = None
    display_name: str | None = None
    is_admin: bool = False
    # so the client can nag gently rather than guessing. Null on every account
    # that was never asked — see the model — which is not the same as false.
    email_verified_at: datetime | None = None

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
    # whether this install offers a "create an account" link at all
    open_signup: bool = False
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
        return MeOut(multi_user=True, needs_setup=True, open_signup=settings.open_signup)
    uid = request.session.get("uid")
    user = db.get(User, uid) if uid else None
    return MeOut(
        multi_user=True,
        open_signup=settings.open_signup,
        user=UserOut.model_validate(user) if user else None,
    )


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


# --- Signing yourself up, and getting back in ------------------------------
# All of this is for the hosted service. A self-hosted install has OPEN_SIGNUP
# off and no mail provider, and none of these routes do anything there except
# the 404 they should.


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=50)


class TokenIn(BaseModel):
    token: str = Field(min_length=8, max_length=200)


class ResetIn(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class DeleteMe(BaseModel):
    password: str | None = None


def _require_open_signup():
    if not multi_user() or not settings.open_signup:
        # 404 rather than 403: on an install that does not offer signup, this
        # route does not exist, and saying "forbidden" only advertises that
        # there is something here to get past.
        raise HTTPException(404, "Not found")


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(
    body: SignupIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Make yourself an account.

    Off unless OPEN_SIGNUP is set, because the default install of this is
    somebody's home server. Turning it on is what makes it a service.
    """
    _require_open_signup()

    key = client_key(request, "signup")
    wait = signups.retry_after(key)
    if wait:
        raise HTTPException(
            429, "Too many accounts from here. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    # This does tell a stranger whether an address has an account, which is a
    # real leak. The alternative — accept every signup and mail the existing
    # holder instead — trades it for a worse one: somebody who genuinely
    # forgot they had signed up gets silence and a form that appeared to work.
    if db.query(User).filter(User.email == body.email).count():
        raise HTTPException(409, "That email already has an account")

    signups.failed(key)
    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    raw = issue_link_token(db, user, AuthToken.VERIFY, timedelta(hours=VERIFY_HOURS))
    background.add_task(send_verification, user.email, raw, VERIFY_HOURS)

    # Signed in straight away, unverified. Making somebody check their mail
    # before they can look at the thing they just signed up for is how you
    # lose them; verification gates the reset path, not the front door.
    request.session["uid"] = user.id
    return user


@router.post("/verify", status_code=204)
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    """Spend a link from a verification email."""
    user = spend_link_token(db, body.token, AuthToken.VERIFY)
    if user is None:
        raise HTTPException(400, "That link has expired or has already been used")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()


@router.post("/verify/resend", status_code=204)
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.email_verified_at is not None or not user.email:
        return  # nothing to do, and saying so would be noise
    wait = mails.retry_after(client_key(request, user.email))
    if wait:
        raise HTTPException(
            429, "Another email is already on its way.",
            headers={"Retry-After": str(wait)},
        )
    mails.failed(client_key(request, user.email))
    raw = issue_link_token(db, user, AuthToken.VERIFY, timedelta(hours=VERIFY_HOURS))
    background.add_task(send_verification, user.email, raw, VERIFY_HOURS)


@router.post("/forgot", status_code=204)
def forgot_password(
    body: EmailIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send a reset link, if there is anybody to send it to.

    Always 204, whatever happens. An address that has no account and one that
    does must be indistinguishable from out here, or this becomes a way to
    ask which of a list of people uses the service.
    """
    if not multi_user():
        raise HTTPException(404, "Not found")

    key = client_key(request, body.email)
    if mails.retry_after(key):
        return  # silently, for the same reason
    mails.failed(key)

    user = db.query(User).filter(User.email == body.email).one_or_none()
    if user is None or not user.email:
        return
    raw = issue_link_token(db, user, AuthToken.RESET, timedelta(minutes=RESET_MINUTES))
    background.add_task(send_reset, user.email, raw, RESET_MINUTES)


@router.post("/reset", status_code=204)
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    """Set a new password from an emailed link.

    Not signed in afterwards, deliberately: whoever redeems this has proved
    they can read the mailbox, which is worth a new password and not worth a
    session on somebody else's phone.
    """
    user = spend_link_token(db, body.token, AuthToken.RESET)
    if user is None:
        raise HTTPException(400, "That link has expired or has already been used")
    user.password_hash = hash_password(body.password)
    # Reading the mailbox is the same proof verification asks for, so somebody
    # who resets an unverified account has just verified it.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    request.session.clear()


@router.delete("/me", status_code=204)
def delete_own_account(
    body: DeleteMe,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Delete your own account and everything in it.

    Google Play requires this to exist in the app and at a public URL, and it
    should exist regardless — an account you cannot leave is not really yours.
    The owner is refused: deleting user 1 on a self-hosted install would leave
    a database nobody can sign into.
    """
    if user.id == OWNER_ID:
        raise HTTPException(400, "The owner account can't be deleted")
    if user.password_hash and not verify_password(body.password or "", user.password_hash):
        raise HTTPException(403, "Password is wrong")
    # copies, wanted list, binders, tags, settings and tokens all cascade
    db.delete(user)
    db.commit()
    request.session.clear()


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
