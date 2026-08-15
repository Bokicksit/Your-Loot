from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BarcodeCache(Base):
    """What a barcode turned out to be, kept so nobody has to ask twice.

    Shared by everyone on the install, like the catalogue is: a barcode means
    the same thing whoever scans it, so the first person to scan one pays for
    the answer and everybody after reads it.
    """

    __tablename__ = "barcode_cache"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    # the provider's answer as given — titles and retailer photographs
    payload: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    found: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now()
    )
