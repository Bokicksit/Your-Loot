import ipaddress
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import current_user
from app.config import settings
from app.imgauth import DEFAULT_TTL as IMAGE_TTL, sign as sign_image
from app.trim import trim_border

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 15 * 1024 * 1024
MAX_LABEL = f"{MAX_BYTES // (1024 * 1024)} MB"
TOO_LARGE = f"image is too large ({MAX_LABEL} max)"
CHUNK = 1024 * 1024


@router.get("/link")
def signed_link(name: str, user=Depends(current_user)):
    """A URL for a photograph that works without a cookie.

    For clients holding a bearer token rather than a session — a phone app,
    say — because an `<img>` tag cannot send an Authorization header and so
    has no other way to prove who is asking. Signed in to ask for one; the
    link then stands on its own for an hour.
    """
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "not a filename")
    return {"url": f"/images/{name}?token={sign_image(name)}", "expires_in": IMAGE_TTL}


@router.post("")
async def upload_image(file: UploadFile):
    """Store an upload in IMAGE_DIR (bind-mounted to a TrueNAS dataset) and
    return the /images/ URL to save on an item.

    Streamed a chunk at a time rather than read() into one buffer: a phone
    photo is a few MB, but nothing stops a 20 MB original, and the size has to
    be known before it lands on the dataset anyway."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"unsupported file type {ext!r}")

    name = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.image_dir) / name
    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > MAX_BYTES:
                    raise HTTPException(400, TOO_LARGE)
                out.write(chunk)
    except Exception:
        # never leave a half-written or oversized file behind
        dest.unlink(missing_ok=True)
        raise
    if not written:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "that file is empty")
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
        raise HTTPException(400, TOO_LARGE)

    # catalogue art arrives padded onto whatever canvas the shop uses; the
    # thumbnail takes its shape from the file, so the padding has to go
    body = trim_border(resp.content)
    name = f"{uuid.uuid4().hex}{ext}"
    (Path(settings.image_dir) / name).write_bytes(body)
    return {"url": f"/images/{name}"}
