from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiToken(TimestampMixin, Base):
    """A bearer token, for a client that cannot hold a cookie.

    The web UI keeps using its session cookie and is untouched. This exists
    for everything that is not a browser on the same origin: a phone app, a
    script, a second machine. A cookie cannot serve those — from another
    origin it is a third-party cookie, which mobile webviews increasingly
    refuse outright.

    The token itself is never stored. Only its SHA-256 is kept, so a copy of
    this table is not a copy of everybody's access; the raw value is returned
    once, at creation, and cannot be recovered afterwards. `prefix` is the
    first few characters, kept in the clear purely so a person can tell two
    tokens apart in a list.

    Revoking sets a timestamp rather than deleting the row: "this token was
    used until Tuesday and then withdrawn" is worth being able to see.
    """

    __tablename__ = "api_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # what it is for, in your own words — "my phone", "the backup script"
    name: Mapped[str] = mapped_column(String(60))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(12))
    # What it may do. "full" is the account; "sync" may do one thing — push a
    # collection into this account — and is refused everywhere else. It is the
    # scope for a token that has to live on another machine.
    scope: Mapped[str] = mapped_column(String(12), default="full", server_default="full")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class AuthToken(TimestampMixin, Base):
    """A single-use link sent to an email address.

    Two jobs, one shape: proving an address belongs to whoever signed up, and
    letting somebody back in who has forgotten their password. Both are "hold
    this secret for a while, spend it once", and splitting them into two
    tables would only mean writing the expiry logic twice.

    Stored as a SHA-256 like ApiToken, and for the same reason — a leaked
    copy of this table must not be a leaked copy of everybody's password
    reset. The raw value exists only in the email.

    `used_at` rather than deleting the row: a reset that was already spent
    should say so, and the row is the evidence. It also means a link mailed
    twice cannot be redeemed twice.
    """

    __tablename__ = "auth_token"

    VERIFY = "verify"
    RESET = "reset"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))  # verify | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
