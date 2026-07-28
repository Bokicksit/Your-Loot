import ipaddress
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 15 * 1024 * 1024


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


class FetchBody(BaseModel):
    url: str


def _reject_private(host: str):
    """Don't let a pasted URL make the API poke around the LAN (SSRF)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, "couldn't resolve that host")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(400, "that address isn't allowed")


@router.post("/fetch")
def fetch_image(body: FetchBody):
    """Store a copy of an image from a pasted URL — e.g. the card art from
    pokemon.com's asset CDN. Copying it locally means the picture keeps
    working if the source moves or blocks hotlinking."""
    parsed = urlparse(body.url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(400, "paste a full http(s) image URL")
    _reject_private(parsed.hostname)

    try:
        resp = httpx.get(
            body.url.strip(),
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "your-loot/1.0"},
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"source returned {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"couldn't fetch that URL: {e}")

    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    ext = EXT_BY_TYPE.get(ctype)
    if not ext:
        raise HTTPException(400, f"that URL isn't an image (got {ctype or 'unknown'})")
    if len(resp.content) > MAX_BYTES:
        raise HTTPException(400, "image is too large (15 MB max)")

    name = f"{uuid.uuid4().hex}{ext}"
    (Path(settings.image_dir) / name).write_bytes(resp.content)
    return {"url": f"/images/{name}"}
