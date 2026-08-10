from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class RecordAttrsOut(BaseModel):
    artist: str | None = None
    label: str | None = None
    catalog_number: str | None = None
    format: str | None = None
    speed: str | None = None
    pressing: str | None = None
    release_year: int | None = None
    country: str | None = None
    barcode: str | None = None
    track_count: int | None = None
    tracklist: str | None = None


class RecordOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: RecordAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class RecordListOut(BaseModel):
    total: int
    items: list[RecordOut]


class RecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    artist: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    catalog_number: str | None = Field(default=None, max_length=60)
    format: str | None = Field(default=None, max_length=40)
    speed: str | None = Field(default=None, max_length=10)
    pressing: str | None = Field(default=None, max_length=200)
    release_year: int | None = None
    country: str | None = Field(default=None, max_length=60)
    barcode: str | None = Field(default=None, max_length=20)
    track_count: int | None = None
    tracklist: str | None = None
    image_url: str | None = None
    notes: str | None = None


class RecordUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    artist: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    catalog_number: str | None = Field(default=None, max_length=60)
    format: str | None = Field(default=None, max_length=40)
    speed: str | None = Field(default=None, max_length=10)
    pressing: str | None = Field(default=None, max_length=200)
    release_year: int | None = None
    country: str | None = Field(default=None, max_length=60)
    barcode: str | None = Field(default=None, max_length=20)
    track_count: int | None = None
    tracklist: str | None = None
    image_url: str | None = None
    notes: str | None = None
