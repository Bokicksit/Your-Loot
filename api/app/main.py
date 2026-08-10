from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import session_secret
from app.config import settings
from app.routers import (
    auth,
    backup,
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

# nginx fronts this in deployment; permissive CORS is for `npm run dev` only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(collection.router)
app.include_router(games.router)
app.include_router(movies.router)
app.include_router(books.router)
app.include_router(records.router)
app.include_router(lego.router)
app.include_router(comics.router)
app.include_router(images.router)
app.include_router(backup.router)
app.include_router(settings_router.router)
app.include_router(lookup.router)
app.include_router(tags.router)

Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.image_dir), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}
