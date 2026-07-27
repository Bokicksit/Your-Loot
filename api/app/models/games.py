from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Platform(Base):
    """Lookup table so games and hardware share one canonical platform list.
    Seeded with common consoles in the initial migration."""

    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    abbreviation: Mapped[str | None] = mapped_column(String(20))


class GameAttrs(Base):
    __tablename__ = "game_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"))
    region: Mapped[str | None] = mapped_column(String(20))  # NTSC-U/PAL/NTSC-J...
    is_hardware: Mapped[bool] = mapped_column(Boolean, default=False)
    # NOTE: completeness (loose/CIB/sealed) lives on the `owned` record — it
    # describes your copy, not the game itself.
    # info panel metadata, captured from IGDB at add time (manual adds: blank)
    summary: Mapped[str | None] = mapped_column(Text)
    release_year: Mapped[int | None] = mapped_column()
    genres: Mapped[str | None] = mapped_column(String(120))
    developer: Mapped[str | None] = mapped_column(String(100))
    publisher: Mapped[str | None] = mapped_column(String(100))

    item = relationship("CollectionItem", back_populates="game_attrs")
    platform = relationship("Platform")
