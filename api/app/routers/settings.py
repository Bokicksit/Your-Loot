import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.limits import binder_limit, card_limit, dex_limit, limited
from app.models import CardAttrs, CollectionItem, Module, Owned, Setting, User
from app.modules import available
from app.plans import paid_modules, subscribed

router = APIRouter(prefix="/api/settings", tags=["settings"])


# What this install offers, not what the code can draw — a person cannot
# switch on a collection their server does not carry. See app/modules.py.
MODULES = available()
# Things that can be drawn as tiles. The wanted list and the shelf of binders
# are views rather than collections — neither can be turned on or off — but
# both have the same two layouts, so they belong in this list and nowhere else.
VIEWS = MODULES + ["wanted", "binders"]
# stored as comma-separated strings in the key/value settings table
DEFAULTS = {
    "owner_name": None,          # None = never set, drives first-run onboarding
    "enabled_modules": ",".join(MODULES),
    "dex_cols": "4",
    "card_cols": "3",
    # Which collections draw tiles instead of rows. Cards has always been
    # tiles and everything else has always been rows, so this default is
    # what the app already looked like before the toggle existed.
    "tile_modules": "cards",
    # How each collection was last left: its sort, and whatever it was
    # filtered by. One JSON blob rather than twenty keys, because the set
    # differs per collection and grows whenever a filter does.
    "list_prefs": "{}",
    "show_binder_in_collection": "false",
    "default_region": "NTSC-U",
    # what a book is, unless you say otherwise — most shelves lean one way
    "default_book_format": "Hardcover",
    "default_book_jacket": "With jacket",
}


def _csv(v: str | None) -> list[str]:
    return [x for x in (v or "").split(",") if x]


def _prefs(v: str | None) -> dict:
    """Stored as JSON in a text column. Anything unreadable is treated as
    "no preference" — a corrupt blob should lose a sort order, not the page."""
    try:
        out = json.loads(v or "{}")
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


class SettingsOut(BaseModel):
    owner_name: str | None = None
    enabled_modules: list[str] = []
    # What this install carries at all, which is not the same as what you have
    # switched on. Sent so the settings screen can offer toggles for the
    # collections that exist rather than for every one the code can draw.
    available_modules: list[str] = []
    # Which of those cost money here, and whether this account has paid.
    # Both empty and false on a self-hosted install, where nothing is paid.
    paid_modules: list[str] = []
    subscribed: bool = False
    # Whether the Japanese catalogue was ever seeded here.
    #
    # It is opt-in and most installs will never run it, so the controls that
    # only make sense alongside it — the JP tick when adding a card, the
    # Japanese switch in a binder's settings — have to know whether to exist.
    # A tick that can only ever return nothing is worse than no tick.
    has_japanese: bool = False
    # What a free account gets here, so the screens can say so before somebody
    # runs into it. All zero on a self-hosted install, where nothing is
    # limited and none of this is drawn.
    limits: dict = {}
    dex_cols: int = 4
    card_cols: int = 3
    tile_modules: list[str] = []
    list_prefs: dict = {}
    show_binder_in_collection: bool = False
    default_region: str = "NTSC-U"
    default_book_format: str = "Hardcover"
    default_book_jacket: str = "With jacket"
    # True until onboarding has been completed at least once
    needs_onboarding: bool = False


class SettingsUpdate(BaseModel):
    """Only fields present in the request change."""

    owner_name: str | None = Field(default=None, max_length=50)
    enabled_modules: list[str] | None = None
    dex_cols: int | None = Field(default=None, ge=2, le=8)
    card_cols: int | None = Field(default=None, ge=2, le=8)
    tile_modules: list[str] | None = None
    list_prefs: dict | None = None
    show_binder_in_collection: bool | None = None
    default_region: str | None = Field(default=None, max_length=20)
    default_book_format: str | None = Field(default=None, max_length=30)
    default_book_jacket: str | None = Field(default=None, max_length=30)


def _current(db: Session, user_id: int) -> SettingsOut:
    who = db.get(User, user_id)
    stored = {
        s.key: s.value
        for s in db.query(Setting).filter(Setting.user_id == user_id).all()
    }
    raw = {**DEFAULTS, **stored}
    enabled = [m for m in _csv(raw["enabled_modules"]) if m in MODULES]
    return SettingsOut(
        owner_name=raw["owner_name"],
        enabled_modules=enabled or MODULES,
        available_modules=MODULES,
        paid_modules=[m for m in paid_modules() if m in MODULES],
        subscribed=subscribed(who),
        # exists() rather than a count: the answer is a yes or no and the
        # index can stop at the first row
        has_japanese=bool(
            db.scalar(select(CardAttrs.item_id).where(CardAttrs.language == "ja").limit(1))
        ),
        limits={
            # what applies to this person right now, not what the install
            # could impose — a supporter is told nothing is limited, because
            # for them nothing is
            "applies": limited(who),
            "cards": card_limit(),
            "dex": dex_limit(),
            "binders": binder_limit(),
            "cards_held": db.scalar(
                select(func.count())
                .select_from(Owned)
                .join(CollectionItem, CollectionItem.id == Owned.item_id)
                .where(
                    Owned.user_id == user_id,
                    CollectionItem.module == Module.cards.value,
                )
            ) or 0,
        },
        dex_cols=int(raw["dex_cols"] or 4),
        card_cols=int(raw["card_cols"] or 3),
        tile_modules=[m for m in _csv(raw["tile_modules"]) if m in VIEWS],
        list_prefs=_prefs(raw["list_prefs"]),
        show_binder_in_collection=str(raw["show_binder_in_collection"]).lower() == "true",
        default_region=raw["default_region"] or "NTSC-U",
        default_book_format=raw["default_book_format"] or "Hardcover",
        default_book_jacket=raw["default_book_jacket"] or "With jacket",
        # the row only exists once onboarding has been submitted, so its
        # absence — not an empty name — is what asks the question
        needs_onboarding="owner_name" not in stored,
    )


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _current(db, user.id)


@router.put("", response_model=SettingsOut)
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, dict):
            value = json.dumps(value, separators=(",", ":"))
        elif isinstance(value, list):
            allowed = VIEWS if key == "tile_modules" else MODULES
            value = ",".join(v for v in value if v in allowed)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        elif value is not None:
            value = str(value).strip()
        row = db.get(Setting, (user.id, key))
        if row is None:
            db.add(Setting(user_id=user.id, key=key, value=value))
        else:
            row.value = value
    db.commit()
    return _current(db, user.id)

