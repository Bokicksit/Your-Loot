from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class LegoAttrsOut(BaseModel):
    set_number: str | None = None
    theme: str | None = None
    subtheme: str | None = None
    release_year: int | None = None
    piece_count: int | None = None
    minifig_count: int | None = None
    barcode: str | None = None


class LegoOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: LegoAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None
    # your own words for this item, in this collection only
    tags: list[str] = []


class LegoListOut(BaseModel):
    total: int
    items: list[LegoOut]


class LegoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    set_number: str | None = Field(default=None, max_length=20)
    theme: str | None = Field(default=None, max_length=80)
    subtheme: str | None = Field(default=None, max_length=80)
    release_year: int | None = None
    piece_count: int | None = None
    minifig_count: int | None = None
    barcode: str | None = Field(default=None, max_length=20)
    image_url: str | None = None
    notes: str | None = None


class LegoUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    set_number: str | None = Field(default=None, max_length=20)
    theme: str | None = Field(default=None, max_length=80)
    subtheme: str | None = Field(default=None, max_length=80)
    release_year: int | None = None
    piece_count: int | None = None
    minifig_count: int | None = None
    barcode: str | None = Field(default=None, max_length=20)
    image_url: str | None = None
    notes: str | None = None
