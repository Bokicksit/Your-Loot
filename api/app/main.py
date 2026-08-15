from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import current_user, session_secret
from app.config import origin_list, settings
from app.models import User
from app.modules import available
from app.plans import costs_money, may_open
from app.routers import (
    auth,
    backup,
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

Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.image_dir), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}
