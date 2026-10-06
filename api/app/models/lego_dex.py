from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LegoTile(Base):
    """A LEGO Smart Tag somebody has tapped, and the Pokémon it is.

    A phone's browser can read a Smart Tag's serial number and nothing else —
    the Pokémon is in the chip's memory, which Web NFC does not expose. So the
    first tap asks which Pokémon it is and this row remembers the answer; every
    tap after that is a capture. The serial is the chip's own and unique to the
    physical tile, so two Bidoof tiles are two rows.
    """

    __tablename__ = "lego_tile"
    __table_args__ = (UniqueConstraint("user_id", "serial", name="uq_lego_tile_user_serial"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # lower-case hex, no separators — the way Chrome hands it over, tidied
    serial: Mapped[str] = mapped_column(String(32), nullable=False)
    dex_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
