from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Setting(Base):
    """Tiny key/value store for app-level prefs (owner_name, defaults later)."""

    __tablename__ = "settings"

    # preferences each: "four cards across" is one person's answer
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True, server_default="1",
    )
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class ScreenName(Base):
    """The name somebody chose, once.

    Not changeable. This is not a social network, and a name that never moves
    is a URL that never breaks — no aliases, no redirects, no ambiguity about
    which of somebody's old addresses is the real one.

    A row outlives its owner holding it. When an administrator takes a name
    away it is marked revoked rather than deleted, and the unique index across
    every row means nobody can ever claim it again — not even the person who
    picked it. That is the difference between a revocation and a rename: a
    rename would want the old URL to keep working.
    """

    __tablename__ = "screen_name"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    display: Mapped[str] = mapped_column(String(30), nullable=False)
    revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
