from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class AmiiboAttrsOut(BaseModel):
    amiibo_id: str | None = None
    character: str | None = None
    amiibo_series: str | None = None
    game_series: str | None = None
    figure_type: str | None = None
    release_year: int | None = None
    release_na: str | None = None


class AmiiboOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: AmiiboAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None
    # your own words for this item, in this collection only
    tags: list[str] = []


class AmiiboListOut(BaseModel):
    total: int
    items: list[AmiiboOut]


class AmiiboCreate(BaseModel):
    """Manual entry only — a figure the catalogue has never heard of, which
    with 932 seeded is the exception. The normal path is searching the
    catalogue and adding a copy of what is already there."""

    title: str = Field(min_length=1, max_length=300)
    character: str | None = Field(default=None, max_length=80)
    amiibo_series: str | None = Field(default=None, max_length=80)
    game_series: str | None = Field(default=None, max_length=80)
    figure_type: str | None = Field(default=None, max_length=20)
    release_year: int | None = None
    image_url: str | None = None
    notes: str | None = None


class AmiiboUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    character: str | None = Field(default=None, max_length=80)
    amiibo_series: str | None = Field(default=None, max_length=80)
    game_series: str | None = Field(default=None, max_length=80)
    figure_type: str | None = Field(default=None, max_length=20)
    release_year: int | None = None
    image_url: str | None = None
    notes: str | None = None
