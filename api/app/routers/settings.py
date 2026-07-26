from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsOut(BaseModel):
    # None = never set (drives the first-run prompt); "" = set-but-skipped
    owner_name: str | None = None


class SettingsUpdate(BaseModel):
    owner_name: str = Field(max_length=50)


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    row = db.get(Setting, "owner_name")
    return SettingsOut(owner_name=row.value if row else None)


@router.put("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    row = db.get(Setting, "owner_name")
    if row is None:
        db.add(Setting(key="owner_name", value=body.owner_name.strip()))
    else:
        row.value = body.owner_name.strip()
    db.commit()
    return SettingsOut(owner_name=body.owner_name.strip())
