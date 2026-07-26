from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("")
def list_movies():
    # Phase 2: list/search movies, TMDB-backed metadata + manual edition fields
    # (see app/integrations/tmdb.py)
    raise HTTPException(501, "Movies module is stubbed — coming in phase 2")
