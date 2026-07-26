from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class GameAttrsOut(BaseModel):
    platform_id: int | None = None
    platform_name: str | None = None
    platform_abbr: str | None = None
    region: str | None = None
    is_hardware: bool = False


class GameOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: GameAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class GameListOut(BaseModel):
    total: int
    items: list[GameOut]


class GameCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    platform_id: int | None = None
    region: str | None = None
    is_hardware: bool = False
    image_url: str | None = None
    notes: str | None = None
    igdb_id: int | None = None  # set when the entry came from IGDB search
