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
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def active(self) -> bool:
        return self.revoked_at is None
