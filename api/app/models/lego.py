from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LegoAttrs(Base):
    """A set, identified by its set number. Piece and minifig counts are here
    rather than on the copy because they describe the set as published — what
    a given box is actually missing is per-copy."""

    __tablename__ = "lego_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    set_number: Mapped[str | None] = mapped_column(String(20), index=True)
    theme: Mapped[str | None] = mapped_column(String(80), index=True)
    subtheme: Mapped[str | None] = mapped_column(String(80))
    release_year: Mapped[int | None] = mapped_column()
    piece_count: Mapped[int | None] = mapped_column()
    minifig_count: Mapped[int | None] = mapped_column()
    barcode: Mapped[str | None] = mapped_column(String(20), index=True)

    item = relationship("CollectionItem", back_populates="lego_attrs")
