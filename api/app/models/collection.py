from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Owned(TimestampMixin, Base):
    """One row per physical copy — owning duplicates is normal for cards."""

    __tablename__ = "owned"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), index=True
    )
    condition: Mapped[str | None] = mapped_column(String(20))  # NM/LP/MP/HP/DMG or free-form
    # games only: loose/CIB/sealed — per copy, since you can own a loose one
    # and later add a CIB one
    completeness: Mapped[str | None] = mapped_column(String(20))
    # cards only: grading ("PSA" + "9"); both null = raw
    grader: Mapped[str | None] = mapped_column(String(10))
    grade: Mapped[str | None] = mapped_column(String(6))
    # cards only: this specific copy sits in the Pokédex binder (opt-in)
    in_binder: Mapped[bool] = mapped_column(default=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="owned")


class Wanted(TimestampMixin, Base):
    __tablename__ = "wanted"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_item.id", ondelete="CASCADE"), unique=True
    )
    priority: Mapped[int | None] = mapped_column()  # 1 = grail, higher = lower prio
    notes: Mapped[str | None] = mapped_column(Text)

    item = relationship("CollectionItem", back_populates="wanted")
