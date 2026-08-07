from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

MODULES = [
    "cards", "games", "hardware", "movies", "books", "records", "lego", "comics",
]
# stored as comma-separated strings in the key/value settings table
DEFAULTS = {
    "owner_name": None,          # None = never set, drives first-run onboarding
    "enabled_modules": ",".join(MODULES),
    "favorite_modules": "",
    "dex_cols": "4",
    "card_cols": "3",
    "show_binder_in_collection": "false",
    "default_region": "NTSC-U",
}


def _csv(v: str | None) -> list[str]:
    return [x for x in (v or "").split(",") if x]


class SettingsOut(BaseModel):
    owner_name: str | None = None
    enabled_modules: list[str] = []
    favorite_modules: list[str] = []
    dex_cols: int = 4
    card_cols: int = 3
    show_binder_in_collection: bool = False
    default_region: str = "NTSC-U"
    # True until onboarding has been completed at least once
    needs_onboarding: bool = False


class SettingsUpdate(BaseModel):
    """Only fields present in the request change."""

    owner_name: str | None = Field(default=None, max_length=50)
    enabled_modules: list[str] | None = None
    favorite_modules: list[str] | None = None
    dex_cols: int | None = Field(default=None, ge=2, le=8)
    card_cols: int | None = Field(default=None, ge=2, le=8)
    show_binder_in_collection: bool | None = None
    default_region: str | None = Field(default=None, max_length=20)


def _current(db: Session) -> SettingsOut:
    stored = {s.key: s.value for s in db.query(Setting).all()}
    raw = {**DEFAULTS, **stored}
    enabled = [m for m in _csv(raw["enabled_modules"]) if m in MODULES]
    return SettingsOut(
        owner_name=raw["owner_name"],
        enabled_modules=enabled or MODULES,
        favorite_modules=[m for m in _csv(raw["favorite_modules"]) if m in enabled],
        dex_cols=int(raw["dex_cols"] or 4),
        card_cols=int(raw["card_cols"] or 3),
        show_binder_in_collection=str(raw["show_binder_in_collection"]).lower() == "true",
        default_region=raw["default_region"] or "NTSC-U",
        # the row only exists once onboarding has been submitted, so its
        # absence — not an empty name — is what asks the question
        needs_onboarding="owner_name" not in stored,
    )


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _current(db)


@router.put("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, list):
            value = ",".join(v for v in value if v in MODULES)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        elif value is not None:
            value = str(value).strip()
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return _current(db)
