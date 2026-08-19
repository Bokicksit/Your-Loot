from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.auth import current_user, session_secret
from app.config import origin_list, settings
from app.db import get_db
from app.imgauth import verify as verify_image_token
from app.models import User
from app.modules import available
from app.plans import costs_money, may_open
from app.routers import (
    admin,
    auth,
    backup,
    billing,
    binders,
    books,
    cards,
    collection,
    comics,
    games,
    images,
    lego,
    lookup,
    movies,
    profile,
    records,
    share,
    tags,
)
from app.routers import settings as settings_router
from app.version import VERSION

app = FastAPI(title="Your Loot", version=VERSION)

# Signed cookie, http-only, not readable by scripts. Lax rather than strict so
# following a link into the app doesn't land you on a signed-out page.
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie="loot_session",
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 24 * 30,
)

# Named origins rather than "*", which was both too permissive and useless:
# a browser refuses to send credentials to a wildcard origin, so the old
# setting could never have supported a real cross-origin client anyway.
# Same-origin needs no entry here at all — nginx serves both halves in
# production, and that path never reaches CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(billing.router)
app.include_router(collection.router)

# A collection this install does not offer is not registered at all, so its
# routes 404 the way any other unknown path does. Hiding the tab and leaving
# /api/movies answering would not be hiding it — it would be moving it
# somewhere only the curious find. `hardware` has no router of its own; it is
# served by games.
_ROUTERS = {
    "cards": cards.router,
    "games": games.router,
    "movies": movies.router,
    "books": books.router,
    "records": records.router,
    "lego": lego.router,
    "comics": comics.router,
}
def _paywall(module: str):
    """Refuse a collection this install charges for to somebody who has not
    paid. Attached to the whole router rather than to each endpoint, because
    a paywall with one route missing is not a paywall."""

    def guard(user: User = Depends(current_user)):
        if not may_open(user, module):
            raise HTTPException(
                402,
                f"{module.title()} is part of the paid plan. "
                "Your collection is safe and still here.",
            )

    return guard


for _name in available():
    _router = _ROUTERS.get(_name)
    if _router is None:
        continue
    # Empty on every self-hosted install, so this list is empty and nothing
    # anywhere is guarded.
    _guards = [Depends(_paywall(_name))] if costs_money(_name) else []
    app.include_router(_router, dependencies=_guards)

app.include_router(images.router)
app.include_router(backup.router)
app.include_router(settings_router.router)
app.include_router(lookup.router)
app.include_router(tags.router)
app.include_router(binders.router)
app.include_router(share.router)
# /api/profile needs a session; /u/<name> is the one page that must not,
# so the guard is on the handlers rather than the router.
app.include_router(profile.router)

Path(settings.image_dir).mkdir(parents=True, exist_ok=True)


@app.get("/images/{name}")
def uploaded_image(name: str, request: Request, token: str | None = None,
                   db: Session = Depends(get_db)):
    """An uploaded photograph, to somebody entitled to see it.

    This was a StaticFiles mount, which is to say it was public: anybody who
    had a URL could fetch that picture forever, signed in or not. Fine behind
    a home router and wrong on a service.

    404 rather than 403 for a refusal, deliberately — a 403 confirms the file
    exists, which is half of what somebody guessing wants to know.
    """
    # Nothing but a bare filename. A name that can climb out of the directory
    # turns this route into "read any file on the server".
    #
    # Every response leaving here says "private", because a CDN in front of
    # the service caches images by file extension unless told otherwise —
    # which cached two different disasters at once. A 404 from an outage got
    # stamped cacheable, so phones kept showing broken covers for hours after
    # the server was healed; and a 200 authorised by somebody's session got
    # cached at the edge, where anybody could fetch it with no session at
    # all. "Private" keeps the browser's own cache and forbids the shared
    # one, which is exactly the split an authorised response needs.
    refuse = PlainTextResponse(
        "Not found", status_code=404, headers={"Cache-Control": "no-store"}
    )
    if "/" in name or "\\" in name or name.startswith("."):
        return refuse

    allowed = verify_image_token(name, token)
    if not allowed:
        try:
            allowed = current_user(request, db) is not None
        except HTTPException:
            allowed = False
    if not allowed:
        return refuse

    path = Path(settings.image_dir) / name
    if not path.is_file():
        return refuse
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}
