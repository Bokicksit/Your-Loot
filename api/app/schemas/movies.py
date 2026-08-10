from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class MovieAttrsOut(BaseModel):
    format: str | None = None
    edition: str | None = None
    region_code: str | None = None
    genre: str | None = None
    overview: str | None = None
    tmdb_id: int | None = None


class MovieOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: MovieAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None
    # your own words for this item, in this collection only
    tags: list[str] = []


class MovieListOut(BaseModel):
    total: int
    items: list[MovieOut]


class MovieUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    format: str | None = None
    edition: str | None = None
    region_code: str | None = None
    genre: str | None = None
    image_url: str | None = None
    notes: str | None = None


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    format: str | None = None
    edition: str | None = None
    region_code: str | None = None
    genre: str | None = None
    overview: str | None = None
    image_url: str | None = None
    notes: str | None = None
    tmdb_id: int | None = None  # metadata link; duplicates allowed (editions)
