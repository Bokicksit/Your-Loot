from sqlalchemy import BigInteger, ForeignKey, Integer, String
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
    # "en", "ja". Identity is kept by UNIQUE(source, external_id) instead —
    # this is here so the app can ask questions about the card rather than
    # about where it was seeded from.
    language: Mapped[str] = mapped_column(
        String(5), default="en", server_default="en", index=True, nullable=False
    )
    # The English species name, on a card that is not printed in English.
    # Borrowed from the dex number so リザードン can be found by typing
    # Charizard; null where the title already is the English name.
    name_en: Mapped[str | None] = mapped_column(String(120))
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
    # What this card looks like, in 64 bits — see app/arthash.py. Null until
    # seed/hash_cards.py has been over the catalogue, and null forever for
    # the roughly one card in twenty that has no artwork to fingerprint.
    art_hash: Mapped[int | None] = mapped_column(BigInteger)
    set_total: Mapped[int | None] = mapped_column()  # printed size: "91/108" -> 108
    set_year: Mapped[int | None] = mapped_column()  # set release year (from dump)
    set_abbr: Mapped[str | None] = mapped_column(String(10))  # printed code: MEW, JTG
    # Which printings this card exists in lives in `card_printing`, one row
    # each — see CardPrinting below. It was three booleans once, which could
    # not tell a parallel from a Poké Ball parallel.

    item = relationship("CollectionItem", back_populates="card_attrs")


class CardPrinting(Base):
    """One way a card was printed.

    The card list booklet that ships with a set is the model for this: a row
    of boxes beside each card, one per printing, and not the same boxes for
    every card — Exeggcute has four, an ACE SPEC has one.

    `code` is our own short name for the whole combination, because it is what
    a binder slot stores and a slot key has twenty characters. The parts are
    kept beside it so the binder can say "Poké Ball parallel" in the booklet's
    words rather than decoding a string.
    """

    __tablename__ = "card_printing"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # normal|reverse|holo
    foil: Mapped[str | None] = mapped_column(String(20))
    stamp: Mapped[str | None] = mapped_column(String(30))
    size: Mapped[str | None] = mapped_column(String(20))
    # Written down rather than worked out from the code. A set that invents a
    # foil should name it correctly without anybody editing this app.
    label: Mapped[str | None] = mapped_column(String(80))
    short: Mapped[str | None] = mapped_column(String(24))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
