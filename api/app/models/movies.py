from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MovieAttrs(Base):
    __tablename__ = "movie_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    format: Mapped[str | None] = mapped_column(String(30))  # 4K UHD/Blu-ray/DVD/VHS
    edition: Mapped[str | None] = mapped_column(String(100))  # Steelbook, Criterion…
    region_code: Mapped[str | None] = mapped_column(String(10))
    genre: Mapped[str | None] = mapped_column(String(30))  # primary genre
    # metadata pointer only — NOT unique; the same film can exist once per
    # physical edition (see migration 0003)
    tmdb_id: Mapped[int | None] = mapped_column()

    item = relationship("CollectionItem", back_populates="movie_attrs")
