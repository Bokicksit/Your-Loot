from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class GameAttrsOut(BaseModel):
    platform_id: int | None = None
    platform_name: str | None = None
    platform_abbr: str | None = None
    region: str | None = None
    is_hardware: bool = False
    summary: str | None = None
    release_year: int | None = None
    genres: str | None = None
    developer: str | None = None
    publisher: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    working: str | None = None
    parent_id: int | None = None


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


class GameUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    platform_id: int | None = None
    region: str | None = None
    is_hardware: bool | None = None
    image_url: str | None = None
    notes: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    working: str | None = None
    parent_id: int | None = None


class GameCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    platform_id: int | None = None
    region: str | None = None
    is_hardware: bool = False
    image_url: str | None = None
    notes: str | None = None
    igdb_id: int | None = None  # set when the entry came from IGDB search
    summary: str | None = None
    release_year: int | None = None
    genres: str | None = None
    developer: str | None = None
    publisher: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    working: str | None = None
    parent_id: int | None = None
