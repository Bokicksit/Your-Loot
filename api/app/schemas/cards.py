from pydantic import BaseModel, ConfigDict

from app.schemas.common import OwnedOut, WantedOut


class CardAttrsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    set_code: str | None = None
    set_name: str | None = None
    card_number: str | None = None
    rarity: str | None = None
    national_dex_no: int | None = None
    variant: str | None = None


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    image_url: str | None = None
    attrs: CardAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None


class CardListOut(BaseModel):
    total: int
    items: list[CardOut]


class PokedexEntry(BaseModel):
    dex_no: int
    # first owned card's data (or first card if none owned) represents the slot
    display_title: str
    display_image: str | None = None
    owned_count: int
    card_count: int
    cards: list[CardOut]


class PokedexOut(BaseModel):
    entries: list[PokedexEntry]
