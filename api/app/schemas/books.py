from pydantic import BaseModel, Field

from app.schemas.common import OwnedOut, WantedOut


class BookAttrsOut(BaseModel):
    author: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    format: str | None = None
    edition: str | None = None
    publish_year: int | None = None
    page_count: int | None = None
    series: str | None = None
    blurb: str | None = None


class BookOut(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    notes: str | None = None
    attrs: BookAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class BookListOut(BaseModel):
    total: int
    items: list[BookOut]


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: str | None = Field(default=None, max_length=200)
    publisher: str | None = Field(default=None, max_length=120)
    isbn: str | None = Field(default=None, max_length=20)
    format: str | None = Field(default=None, max_length=30)
    edition: str | None = Field(default=None, max_length=100)
    publish_year: int | None = None
    page_count: int | None = None
    series: str | None = Field(default=None, max_length=150)
    blurb: str | None = None
    image_url: str | None = None
    notes: str | None = None


class BookUpdate(BaseModel):
    """PATCH body — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    author: str | None = Field(default=None, max_length=200)
    publisher: str | None = Field(default=None, max_length=120)
    isbn: str | None = Field(default=None, max_length=20)
    format: str | None = Field(default=None, max_length=30)
    edition: str | None = Field(default=None, max_length=100)
    publish_year: int | None = None
    page_count: int | None = None
    series: str | None = Field(default=None, max_length=150)
    blurb: str | None = None
    image_url: str | None = None
    notes: str | None = None
