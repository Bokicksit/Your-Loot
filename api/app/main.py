from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import books, cards, collection, games, images, lookup, movies, records
from app.routers import settings as settings_router


def read_version() -> str:
    """Repo-root VERSION file, bumped +0.01 every commit. Path differs between
    the container (/app/VERSION) and local dev (repo root)."""
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "VERSION", here.parents[2] / "VERSION"):
        if candidate.is_file():
            return candidate.read_text().strip()
    return "dev"


VERSION = read_version()

app = FastAPI(title="Your Loot", version=VERSION)

# nginx fronts this in deployment; permissive CORS is for `npm run dev` only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(collection.router)
app.include_router(games.router)
app.include_router(movies.router)
app.include_router(books.router)
app.include_router(records.router)
app.include_router(images.router)
app.include_router(settings_router.router)
app.include_router(lookup.router)

Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.image_dir), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}
