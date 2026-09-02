from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import OwnedOut, WantedOut


class CardAttrsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: str = "en"
    # the English species name on a card printed in another language
    name_en: str | None = None
    set_code: str | None = None
    set_name: str | None = None
    set_abbr: str | None = None
    set_total: int | None = None
    set_year: int | None = None
    card_number: str | None = None
    rarity: str | None = None
    national_dex_no: int | None = None
    variant: str | None = None
    layer: int = 1


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    image_url: str | None = None
    source: str | None = None  # 'ptcg' (dump) or 'manual' — manual is deletable
    attrs: CardAttrsOut
    owned: list[OwnedOut] = []
    wanted: WantedOut | None = None
    # your own words for this item, in this collection only
    tags: list[str] = []


class CardListOut(BaseModel):
    total: int
    items: list[CardOut]


class CardCreate(BaseModel):
    """Manual catalog entry — for cards the offline dump doesn't carry yet
    (brand-new promos, prereleases, Japanese exclusives)."""

    title: str = Field(min_length=1, max_length=300)
    # Which catalogue it belongs to. A card typed in while looking at the
    # Japanese one is Japanese — otherwise it answers English searches and is
    # let into binders that said English only.
    language: str = Field(default="en", pattern="^(en|ja)$")
    set_name: str | None = Field(default=None, max_length=100)
    set_abbr: str | None = Field(default=None, max_length=10)
    card_number: str | None = Field(default=None, max_length=20)
    set_total: int | None = None
    set_year: int | None = None
    rarity: str | None = Field(default=None, max_length=50)
    national_dex_no: int | None = None
    image_url: str | None = None


class CardUpdate(BaseModel):
    """PATCH body for manual cards — only fields present in the request change."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    set_name: str | None = Field(default=None, max_length=100)
    set_abbr: str | None = Field(default=None, max_length=10)
    card_number: str | None = Field(default=None, max_length=20)
    set_total: int | None = None
    set_year: int | None = None
    rarity: str | None = Field(default=None, max_length=50)
    national_dex_no: int | None = None
    image_url: str | None = None


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


class CardScanOut(CardListOut):
    """What a scan found, and whether it is sure enough to act on.

    The list is deliberately more generous than the confidence: a person
    choosing between eight candidates wants near misses included, while the
    scanner deciding on its own must only do so when it cannot reasonably
    be wrong. One answer, two audiences — see arthash.NEAR and arthash.SURE.
    """

    sure: bool = False


class PriceCheckIn(BaseModel):
    """The cards on the page being looked at, and for each the variant of the
    copy in the slot where the slot has one."""

    item_ids: list[int] = Field(min_length=1, max_length=40)
    variants: dict[int, str | None] = {}


class PriceOut(BaseModel):
    amount: float
    currency: str
    low: float | None = None
    high: float | None = None
    variant: str | None = None
    source: str
    updated: str | None = None


class PriceCheckOut(BaseModel):
    prices: dict[int, PriceOut | None]
    priced: int
    asked: int
    unavailable: bool = False
