from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ImageCopy(Base):
    """Our own copy of a linked picture, kept in case the link breaks.

    One row per catalogue item, whether the fetch worked or not: a failure is
    recorded with when and why, so a dead link is retried on a schedule rather
    than every hour forever. `name` is the file under IMAGE_DIR — named by its
    content, so two items with the same picture share one file — and is null
    while there is no copy yet. See app/copies.py for the rule about whose
    items earn one.
    """

    __tablename__ = "image_copy"

    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True
    )
    source_url: Mapped[str | None] = mapped_column(String(500))
    name: Mapped[str | None] = mapped_column(String(120))
    bytes: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(String(200))
