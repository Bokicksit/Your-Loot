from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Somebody with a collection on this server.

    Single-user installs have exactly one of these and never see a login
    screen — the app signs itself in as the owner. Credentials are therefore
    nullable: a password is something you set on the day you invite a second
    person, not a hurdle put in front of the first.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class ItemOverride(TimestampMixin, Base):
    """What one person changed about a shared catalogue entry.

    The catalogue is common ground — a Charizard is the same card whoever
    holds it — but a photograph of *your* copy and a note about where you
    found it are not. Those used to be written onto the catalogue row itself,
    where they would have been visible to everybody. They live here instead,
    keyed by who wrote them.
    """

    __tablename__ = "item_override"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    image_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
