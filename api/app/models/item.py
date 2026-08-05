import enum

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Module(str, enum.Enum):
    """App-level enum stored as varchar — adding a fourth module is a code
    change plus a new attrs table, never an ALTER TYPE on a PG enum."""

    cards = "cards"
    games = "games"
    movies = "movies"
    books = "books"
    records = "records"
    lego = "lego"
    comics = "comics"


class CollectionItem(TimestampMixin, Base):
    __tablename__ = "collection_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(300))
    image_url: Mapped[str | None] = mapped_column(String(500))
    # Where the item came from ('ptcg' | 'igdb' | 'tmdb' | 'manual') and its id
    # there. UNIQUE(source, external_id) lets seed scripts re-run as upserts.
    source: Mapped[str | None] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    card_attrs = relationship("CardAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    game_attrs = relationship(
        "GameAttrs",
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="GameAttrs.item_id",
    )
    movie_attrs = relationship("MovieAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    book_attrs = relationship("BookAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    record_attrs = relationship("RecordAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    lego_attrs = relationship("LegoAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    comic_attrs = relationship("ComicAttrs", back_populates="item", uselist=False, cascade="all, delete-orphan")
    owned = relationship("Owned", back_populates="item", cascade="all, delete-orphan")
    wanted = relationship("Wanted", back_populates="item", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("uq_item_source_external", "source", "external_id", unique=True),
    )
