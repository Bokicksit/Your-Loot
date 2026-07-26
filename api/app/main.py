from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import cards, collection, games, images, movies

app = FastAPI(title="Get Loot", version="0.1.0")

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
app.include_router(images.router)

Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.image_dir), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok"}
