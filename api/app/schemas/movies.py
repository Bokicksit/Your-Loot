from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class MovieAttrsOut(BaseModel):
    format: str | None = None
    edition: str | None = None
    region_code: str | None = None
    genre: str | None = None
    tmdb_id: int | None = None


class MovieOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: MovieAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class MovieListOut(BaseModel):
    total: int
    items: list[MovieOut]


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    format: str | None = None
    edition: str | None = None
    region_code: str | None = None
    genre: str | None = None
    image_url: str | None = None
    notes: str | None = None
    tmdb_id: int | None = None  # metadata link; duplicates allowed (editions)
