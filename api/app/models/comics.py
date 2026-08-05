from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ComicAttrs(Base):
    """An issue. Series plus issue number isn't unique on its own — Amazing
    Spider-Man #1 exists in half a dozen volumes — so `volume_year` carries the
    run, and `variant` distinguishes covers of the same issue."""

    __tablename__ = "comic_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    series: Mapped[str | None] = mapped_column(String(200), index=True)
    issue_number: Mapped[str | None] = mapped_column(String(20))
    volume_year: Mapped[int | None] = mapped_column()
    publisher: Mapped[str | None] = mapped_column(String(120))
    cover_year: Mapped[int | None] = mapped_column()
    variant: Mapped[str | None] = mapped_column(String(150))
    creators: Mapped[str | None] = mapped_column(String(300))
    barcode: Mapped[str | None] = mapped_column(String(20), index=True)
    blurb: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="comic_attrs")
