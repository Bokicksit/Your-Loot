from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RecordAttrs(Base):
    """A specific pressing, which is what vinyl collectors actually track —
    the same album on a 1977 UK first press and a 2023 reissue are different
    objects with different values. Label + catalogue number identify it."""

    __tablename__ = "record_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    artist: Mapped[str | None] = mapped_column(String(200), index=True)
    label: Mapped[str | None] = mapped_column(String(120))
    catalog_number: Mapped[str | None] = mapped_column(String(60))
    format: Mapped[str | None] = mapped_column(String(40))
    speed: Mapped[str | None] = mapped_column(String(10))
    pressing: Mapped[str | None] = mapped_column(String(200))
    release_year: Mapped[int | None] = mapped_column()
    # the name, not the code: Discogs says "USA & Europe" where MusicBrainz
    # says "XE", and both end up in here
    country: Mapped[str | None] = mapped_column(String(60))
    barcode: Mapped[str | None] = mapped_column(String(20), index=True)
    track_count: Mapped[int | None] = mapped_column()
    # one track to a line, as Discogs lists them for this pressing
    tracklist: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="record_attrs")
