from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AmiiboAttrs(Base):
    """One amiibo, identified by the id burned into the figure itself.

    The head+tail hex pair (0x0438000103000502) is Nintendo's own identity
    for the product — it is what an NFC reader sees — so it is the natural
    external id: stable across installs, which is what lets a personal
    restore find the same figure on another server instead of duplicating it.

    Character, the amiibo series it shipped under and the game series it
    depicts are three different facts — Mario the character has figures in
    the Super Smash Bros. series and the Super Mario series, and they are
    different objects on a shelf.
    """

    __tablename__ = "amiibo_attrs"

    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    # 16 hex digits with the 0x prefix, e.g. 0x0438000103000502
    amiibo_id: Mapped[str | None] = mapped_column(String(20), index=True)
    character: Mapped[str | None] = mapped_column(String(80), index=True)
    amiibo_series: Mapped[str | None] = mapped_column(String(80), index=True)
    game_series: Mapped[str | None] = mapped_column(String(80))
    # Figure / Card / Yarn / Band — the physical kind of thing it is
    figure_type: Mapped[str | None] = mapped_column(String(20), index=True)
    release_year: Mapped[int | None] = mapped_column()
    # the North American date, kept whole for anybody who wants the day
    release_na: Mapped[str | None] = mapped_column(String(10))

    item = relationship("CollectionItem", back_populates="amiibo_attrs")
