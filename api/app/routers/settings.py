import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import Setting, User

router = APIRouter(prefix="/api/settings", tags=["settings"])


MODULES = [
    "cards", "games", "hardware", "movies", "books", "records", "lego", "comics",
]
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
    dex_cols: int = 4
    card_cols: int = 3
    tile_modules: list[str] = []
    list_prefs: dict = {}
    show_binder_in_collection: bool = False
    default_region: str = "NTSC-U"
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


def _current(db: Session, user_id: int) -> SettingsOut:
    stored = {
        s.key: s.value
        for s in db.query(Setting).filter(Setting.user_id == user_id).all()
    }
    raw = {**DEFAULTS, **stored}
    enabled = [m for m in _csv(raw["enabled_modules"]) if m in MODULES]
    return SettingsOut(
        owner_name=raw["owner_name"],
        enabled_modules=enabled or MODULES,
        dex_cols=int(raw["dex_cols"] or 4),
        card_cols=int(raw["card_cols"] or 3),
        tile_modules=[m for m in _csv(raw["tile_modules"]) if m in MODULES],
        list_prefs=_prefs(raw["list_prefs"]),
        show_binder_in_collection=str(raw["show_binder_in_collection"]).lower() == "true",
        default_region=raw["default_region"] or "NTSC-U",
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
            value = ",".join(v for v in value if v in MODULES)
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
