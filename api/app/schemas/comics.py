from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class ComicAttrsOut(BaseModel):
    series: str | None = None
    issue_number: str | None = None
    volume_year: int | None = None
    publisher: str | None = None
    cover_year: int | None = None
    variant: str | None = None
    creators: str | None = None
    barcode: str | None = None
    blurb: str | None = None


class ComicOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: ComicAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class ComicListOut(BaseModel):
    total: int
    items: list[ComicOut]


class ComicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    series: str | None = Field(default=None, max_length=200)
    issue_number: str | None = Field(default=None, max_length=20)
    volume_year: int | None = None
    publisher: str | None = Field(default=None, max_length=120)
    cover_year: int | None = None
    variant: str | None = Field(default=None, max_length=150)
    creators: str | None = Field(default=None, max_length=300)
    barcode: str | None = Field(default=None, max_length=20)
    blurb: str | None = None
    image_url: str | None = None
    notes: str | None = None


class ComicUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    series: str | None = Field(default=None, max_length=200)
    issue_number: str | None = Field(default=None, max_length=20)
    volume_year: int | None = None
    publisher: str | None = Field(default=None, max_length=120)
    cover_year: int | None = None
    variant: str | None = Field(default=None, max_length=150)
    creators: str | None = Field(default=None, max_length=300)
    barcode: str | None = Field(default=None, max_length=20)
    blurb: str | None = None
    image_url: str | None = None
    notes: str | None = None
