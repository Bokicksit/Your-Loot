from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BookAttrs(Base):
    """Per-module attributes for books. The physical details (format,
    edition) are what a shelf cares about; condition and dust-jacket status
    live on the owned copy, since they describe your copy rather than the
    edition."""

    __tablename__ = "book_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    author: Mapped[str | None] = mapped_column(String(200), index=True)
    publisher: Mapped[str | None] = mapped_column(String(120))
    isbn: Mapped[str | None] = mapped_column(String(20), index=True)
    format: Mapped[str | None] = mapped_column(String(30))
    edition: Mapped[str | None] = mapped_column(String(100))
    publish_year: Mapped[int | None] = mapped_column()
    page_count: Mapped[int | None] = mapped_column()
    series: Mapped[str | None] = mapped_column(String(150))
    blurb: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="book_attrs")
