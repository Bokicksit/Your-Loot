from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


def tag_key(name: str) -> str:
    """The form two tags are compared in.

    Free-text tagging rots without this: hip-hop, Hip Hop and HIP-HOP become
    three entries in the filter bar, each holding a third of the records.
    Hyphens and underscores fold to spaces because that is the split people
    actually make by accident; other punctuation is left alone, so R&B stays
    distinct from RB.
    """
    folded = name.replace("-", " ").replace("_", " ")
    return " ".join(folded.split()).casefold()


class Tag(TimestampMixin, Base):
    """A word you filed something under, inside one collection.

    Yours rather than the catalogue's — "want to play" is a fact about you and
    a game, not about the game — so the tag carries `user_id` and every query
    starts from it. That is what keeps one person's labels out of another's,
    for free, rather than by remembering to filter.

    `scope` is the collection as the app presents it, not the module as the
    database stores it. Hardware lives in the games table behind a flag but is
    its own tab, and its own shelf, so it gets its own labels.

    `key` is `name` folded for comparison; `name` keeps what you typed,
    because that is what you want to read back.
    """

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(40))

    items = relationship("ItemTag", back_populates="tag", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "scope", "key", name="uq_tag_user_scope_key"),
    )


class ItemTag(Base):
    """Which items carry a tag. The tag already knows whose it is, so this
    doesn't repeat it — there is no way to reach a row here without going
    through a tag that belongs to somebody."""

    __tablename__ = "item_tag"

    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )

    tag = relationship("Tag", back_populates="items")
