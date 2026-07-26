import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import settings

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("")
async def upload_image(file: UploadFile):
    """Store an upload in IMAGE_DIR (bind-mounted to a TrueNAS dataset) and
    return the /images/ URL to save on an item."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"unsupported file type {ext!r}")
    name = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.image_dir) / name
    dest.write_bytes(await file.read())
    return {"url": f"/images/{name}"}
