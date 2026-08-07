from sqlalchemy import ForeignKey, Integer, String, Text
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
