from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CardAttrs(Base):
    """Per-module attribute table (vs JSONB): typed columns catch bad seed data
    at insert time, and the Pokédex view needs a real index on national_dex_no.
    Adding a module later = a new table like this one; existing tables never change."""

    __tablename__ = "card_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    set_code: Mapped[str | None] = mapped_column(String(30), index=True)
    # denormalized for display; a proper card_set table can come later
    set_name: Mapped[str | None] = mapped_column(String(100))
    card_number: Mapped[str | None] = mapped_column(String(20))  # str: "TG12", "4a"
    rarity: Mapped[str | None] = mapped_column(String(50))
    national_dex_no: Mapped[int | None] = mapped_column(index=True)
    variant: Mapped[str | None] = mapped_column(String(20))  # normal/reverse/holo/full-art
    # binder layer, classified from rarity at seed time:
    # 1 basic (incl. regular ex, vintage holos, golds) / 2 full-art / 3 IR-SIR
    layer: Mapped[int] = mapped_column(default=1, server_default="1")
    set_total: Mapped[int | None] = mapped_column()  # printed size: "91/108" -> 108
    set_year: Mapped[int | None] = mapped_column()  # set release year (from dump)
    set_abbr: Mapped[str | None] = mapped_column(String(10))  # printed code: MEW, JTG
    # Which printings this card exists in — for master-set binders, where a
    # card with a reverse holo gets a slot for each. Null means nobody has
    # asked TCGdex about this set yet, which is not the same as "no reverse
    # exists" and must not be read as it.
    has_normal: Mapped[bool | None] = mapped_column(Boolean)
    has_reverse: Mapped[bool | None] = mapped_column(Boolean)
    has_holo: Mapped[bool | None] = mapped_column(Boolean)

    item = relationship("CollectionItem", back_populates="card_attrs")
