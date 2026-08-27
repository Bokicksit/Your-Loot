import ipaddress
import socket
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

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
async def upload_image(file: UploadFile, user=Depends(current_user)):
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


# A redirect is a second URL somebody else chose, so it gets checked like the
# first one. Enough hops for a CDN that shortens then signs, few enough that a
# loop cannot be used to keep a worker busy.
MAX_HOPS = 5


def _safe_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Resolve a hostname, refuse it if it points anywhere private, and hand
    back the address that passed.

    Returning the address is the point, and the reason this no longer just
    says yes or no. Approving a *name* and then letting the HTTP client look
    it up again leaves a gap between the check and the connection, and DNS is
    something the other side controls: a record with a one-second lifetime can
    answer with a public address for the check and 169.254.169.254 for the
    fetch. Nothing about that is exotic — it is the ordinary way this guard is
    got around. Whoever calls this connects to the address that was cleared,
    so there is no second lookup to poison.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, "couldn't resolve that host")
    cleared = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local  # 169.254/16 — cloud metadata lives here
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(400, "that address isn't allowed")
        cleared.append(ip)
    if not cleared:
        raise HTTPException(400, "couldn't resolve that host")
    # every one of them passed, so the first is as good as any
    return cleared[0]


def _checked_get(url: str) -> httpx.Response:
    """Fetch it, checking every address it sends us to — not just the first.

    The guard used to run once on the pasted hostname and then hand the whole
    job to httpx with follow_redirects=True. That is a hole rather than a
    subtlety: a host anybody controls can answer 302 to 169.254.169.254 or a
    private address, and the check never sees where the request actually
    went. Following the chain here means each hop is a URL that had to pass.

    Each hop then connects to the address that passed, rather than to the name
    that passed — see _safe_address. The name still travels, in the Host
    header and as the TLS server name, so virtual hosts and certificates work
    exactly as they would have; the only thing that changes is that nobody
    gets a second chance to answer the question "where does this point?".
    """
    # a Client rather than httpx.get, because the module-level shortcut takes
    # no `extensions` — and without that there is no way to say "dial here but
    # present this name", which is the whole mechanism below
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for _ in range(MAX_HOPS):
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise HTTPException(400, "paste a full http(s) image URL")
            ip = _safe_address(parsed.hostname)

            literal = f"[{ip}]" if ip.version == 6 else str(ip)
            authority = parsed.netloc.rsplit("@", 1)[-1]  # drop any user:pass
            pinned = parsed._replace(
                netloc=f"{literal}:{parsed.port}" if parsed.port else literal
            ).geturl()
            resp = client.get(
                pinned,
                headers={"User-Agent": "your-loot/1.0", "Host": authority},
                # dial the address, but be the name: TLS is negotiated for the
                # hostname, so the certificate is still checked against it and
                # a wrong one is still refused
                extensions={"sni_hostname": parsed.hostname},
            )
            if not resp.is_redirect:
                return resp
            location = resp.headers.get("location")
            if not location:
                return resp
            # resolved against the name, not the pin, so a relative Location
            # means what the server meant by it
            url = urljoin(url, location)

    raise HTTPException(400, "that URL redirects too many times")


@router.post("/fetch")
def fetch_image(body: FetchBody, user=Depends(current_user)):
    """Store a copy of an image from a pasted URL — e.g. the card art from
    pokemon.com's asset CDN. Copying it locally means the picture keeps
    working if the source moves or blocks hotlinking."""
    try:
        resp = _checked_get(body.url.strip())
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
