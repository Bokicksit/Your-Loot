from pydantic import BaseModel

from app.schemas.common import OwnedOut, WantedOut


class WantedItemOut(BaseModel):
    """A row in the cross-module wanted list. `detail` is a per-module summary
    string built server-side so the UI never needs module-specific logic.
    `facet` is the row's sub-filter value: system for games, genre for movies."""

    item_id: int
    module: str
    title: str
    image_url: str | None = None
    detail: str = ""
    facet: str | None = None
    # left-edge badge: platform abbr for games (logo lookup), format for movies
    badge: str | None = None
    # expandable info, server-built: a facts line + optional longer text
    info_line: str = ""
    info_text: str | None = None
    wanted: WantedOut
    # your own words for this item, carried onto the wanted list because a
    # label like "want to play" is most of the point of still hunting it
    tags: list[str] = []


class ItemStatusOut(BaseModel):
    item_id: int
    owned: list[OwnedOut]
    wanted: WantedOut | None = None
    # your own words for this item, in this collection only
    tags: list[str] = []
