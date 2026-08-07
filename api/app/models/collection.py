from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Owned(TimestampMixin, Base):
    """One row per physical copy — owning duplicates is normal for cards."""

    __tablename__ = "owned"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Defaults to the owner in the database, so every existing INSERT that
    # knows nothing about users keeps working and lands on user 1. Sessions
    # will set it explicitly; the default comes off then.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, server_default="1",
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), index=True
    )
    condition: Mapped[str | None] = mapped_column(String(20))  # NM/LP/MP/HP/DMG or free-form
    # records only: vinyl is graded twice — `condition` is the media grade and
    # this is the sleeve, written together as "VG+/VG"
    sleeve_condition: Mapped[str | None] = mapped_column(String(20))
    # games only: loose/CIB/sealed — per copy, since you can own a loose one
    # and later add a CIB one
    completeness: Mapped[str | None] = mapped_column(String(20))
    # cards only: grading ("PSA" + "9"); both null = raw
    grader: Mapped[str | None] = mapped_column(String(10))
    grade: Mapped[str | None] = mapped_column(String(6))
    # cards only: the number on the slab label. Belongs to the copy, not the
    # card — two people can own the same Charizard, one cert each.
    cert_number: Mapped[str | None] = mapped_column(String(20))
    # cards only: this specific copy sits in the Pokédex binder (opt-in)
    in_binder: Mapped[bool] = mapped_column(default=False, server_default="false")
    # cards only: YOUR copy's print style + promo stamp — the catalog row is
    # the same card whether you pulled the reverse holo or the plain one
    variant: Mapped[str | None] = mapped_column(String(20))  # Non-Holo/Reverse Holo/Holo
    stamp: Mapped[str | None] = mapped_column(String(60))  # "Mega Evolution"…
    notes: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="owned")


class Wanted(TimestampMixin, Base):
    __tablename__ = "wanted"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Defaults to the owner in the database, so every existing INSERT that
    # knows nothing about users keeps working and lands on user 1. Sessions
    # will set it explicitly; the default comes off then.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, server_default="1",
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE")
    )
    priority: Mapped[int | None] = mapped_column()  # 1 = grail, higher = lower prio
    notes: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="wanted")
