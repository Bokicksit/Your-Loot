"""Who is asking.

Two modes, one code path. A single-user install signs itself in as the owner
and never shows a login screen — that is the default, and it is what every
existing install keeps doing after an upgrade. Turn on multi-user and the same
dependency starts reading a session cookie instead.

Passwords are argon2id, which is the current answer and needs no tuning from
us. Sessions are a signed cookie rather than a table: there is no server-side
list to grow, and for an app this size "sign out everywhere" is not worth a
schema for.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine, get_db
from app.models import ApiToken, User

OWNER_ID = 1  # the row migration 0018 seeded from the existing install

_hasher = PasswordHasher()

# A key that has to survive restarts, or every session dies whenever the
# container does. Stored beside the owner's preferences rather than on disk:
# IMAGE_DIR is served as static files, so anything secret in there is one
# guessed URL away from being public.
_SECRET_KEY_SETTING = "_session_secret"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def session_secret() -> str:
    """The cookie-signing key: yours if you set one, otherwise ours.

    Generated on first start and kept, so that self-hosting needs no required
    configuration and sessions still survive a restart. Setting SECRET_KEY
    takes precedence and is what you want if you ever run more than one API
    container, since they must agree.
    """
    if settings.secret_key:
        return settings.secret_key
    with engine.begin() as conn:
        found = conn.execute(
            text("SELECT value FROM settings WHERE user_id = :u AND key = :k"),
            {"u": OWNER_ID, "k": _SECRET_KEY_SETTING},
        ).scalar()
        if found:
            return found
        made = secrets.token_urlsafe(48)
        conn.execute(
            text(
                "INSERT INTO settings (user_id, key, value) VALUES (:u, :k, :v) "
                "ON CONFLICT (user_id, key) DO NOTHING"
            ),
            {"u": OWNER_ID, "k": _SECRET_KEY_SETTING, "v": made},
        )
        return made


def multi_user() -> bool:
    return settings.auth_mode.strip().lower() == "multi"


def owner_locked(db: Session) -> bool:
    """Single-user, but with a lock on the door.

    Radarr and Sonarr do this and Plex does it with a PIN: one account, no
    invitations, no user management — just a password between the internet
    and your shelf. Nobody wants to invent accounts for a house they live in
    alone; plenty of people still want the door shut.

    It is simply "the owner has set a password". No third mode, no extra
    setting: set one and the login screen appears, clear it and it's gone.
    """
    owner = db.get(User, OWNER_ID)
    return bool(owner and owner.password_hash)


def needs_setup(db: Session) -> bool:
    """Multi-user is on but nobody has a password yet.

    The state you land in the first time you flip AUTH_MODE, and the only
    moment an account may be claimed without already being signed in.
    """
    return (
        db.query(User).filter(User.password_hash.isnot(None)).count() == 0
    )


# Tokens are shown once and stored only as a hash, so this is the only way
# back from a presented token to a row.
TOKEN_PREFIX = "ylt_"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> tuple[str, str, str]:
    """(raw, hash, prefix). The raw value is the caller's only copy."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw), raw[:12]


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def user_from_token(request: Request, db: Session) -> User | None:
    """Whoever holds this token, or None if there is no usable one.

    Returns None rather than raising on every failure: a bad token should fall
    through to the cookie path and end at the same "sign in" as anything else,
    not produce a different error that tells an attacker which half was wrong.
    """
    raw = _bearer(request)
    if not raw:
        return None
    row = db.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == hash_token(raw), ApiToken.revoked_at.is_(None)
        )
    )
    if row is None:
        return None
    # Written at most hourly. Knowing a token is still in use is worth having;
    # a database write on every single request to record it is not.
    now = datetime.now(UTC).replace(tzinfo=None)
    if row.last_used_at is None or now - row.last_used_at > timedelta(hours=1):
        row.last_used_at = now
        db.commit()
    return db.get(User, row.user_id)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """The signed-in user, or the owner when this install has only one.

    A bearer token is tried first, because a client that sends one is telling
    you which account it means — and in single-user mode with no password set,
    the cookie path answers "the owner" to everybody, which would quietly
    ignore the token rather than honour it.
    """
    holder = user_from_token(request, db)
    if holder is not None:
        return holder

    if not multi_user():
        owner = db.get(User, OWNER_ID)
        if owner is None:
            # migration 0018 seeds this; if it is gone the install is broken in
            # a way that guessing would only hide
            raise HTTPException(500, "no owner account — check the database")
        if not owner.password_hash:
            return owner  # no password set: the app signs itself in, as always
        if request.session.get("uid") == owner.id:
            return owner
        raise HTTPException(401, "Sign in to continue")

    uid = request.session.get("uid")
    user = db.get(User, uid) if uid else None
    if user is None:
        request.session.clear()
        raise HTTPException(401, "Sign in to continue")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Only an admin can do that")
    return user
