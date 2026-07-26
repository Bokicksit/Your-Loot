from pydantic import BaseModel

from app.schemas.common import OwnedOut, WantedOut


class WantedItemOut(BaseModel):
    """A row in the cross-module wanted list. `detail` is a per-module summary
    string built server-side so the UI never needs module-specific logic."""

    item_id: int
    module: str
    title: str
    image_url: str | None = None
    detail: str = ""
    wanted: WantedOut


class ItemStatusOut(BaseModel):
    item_id: int
    owned: list[OwnedOut]
    wanted: WantedOut | None = None
