from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MovieAttrs(Base):
    __tablename__ = "movie_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    format: Mapped[str | None] = mapped_column(String(30))  # Blu-ray/4K/Steelbook
    edition: Mapped[str | None] = mapped_column(String(100))
    region_code: Mapped[str | None] = mapped_column(String(10))

    item = relationship("CollectionItem", back_populates="movie_attrs")
