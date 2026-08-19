from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import Setting, User
from app.routers import amiibo, books, cards, comics, games, lego, movies, records
from app.routers.collection import wanted_list
from app.share import SPECS, TITLES, build_collection, build_pokedex

router = APIRouter(prefix="/api/share", tags=["share"])

# Rows ship newest-first so the share's two added sorts need only the row's
# position; the collection's own default sort is applied when the file opens.
#
# Each scope's list is fetched by calling the route function the app itself
# uses, rather than by writing the query again here. Tenancy, the games and
# hardware split, and the binder's one-card-per-slot rule are all subtle
# enough that a second implementation would drift — and a share that drifted
# would show somebody a collection that is not quite yours.
LISTS = {
    "records":  lambda **kw: records.list_records(**kw),
    # include_binder, and it is the difference between a collection and a
    # fraction of one. The cards list hides binder-filed cards by default
    # because the app draws the binder on its own page — but a share and a
    # profile have no other page to send somebody to, and for most people the
    # binders are where the collection actually lives. Without this a Pokedex
    # of nine hundred cards exports as the handful that were never filed.
    "cards":    lambda **kw: cards.list_cards(include_binder=True, **kw),
    "games":    lambda **kw: games.list_games(is_hardware=False, **kw),
    "hardware": lambda **kw: games.list_games(is_hardware=True, **kw),
    "movies":   lambda **kw: movies.list_movies(**kw),
    "books":    lambda **kw: books.list_books(**kw),
    "lego":     lambda **kw: lego.list_lego(**kw),
    "comics":   lambda **kw: comics.list_comics(**kw),
    "amiibo":   lambda **kw: amiibo.list_amiibo(**kw),
}

# Under every list's own ceiling, so this asks for nothing a caller over HTTP
# could not.
PAGE = 200


def everything(scope: str, db: Session, user: User) -> list:
    """The whole shelf, however long it is.

    These lists are paged, and a share that quietly stopped at the first page
    would be the worst kind of wrong: it looks complete. So it pages until it
    has the total the list itself reports.
    """
    if scope == "wanted":
        return wanted_list(db=db, user=user, sort="added")

    out, total = [], None
    while total is None or len(out) < total:
        page = LISTS[scope](db=db, user=user, sort="added", limit=PAGE, offset=len(out))
        total = page.total
        if not page.items:  # a row deleted mid-export would otherwise spin here
            break
        out.extend(page.items)
    return out


def _owner_name(db: Session, user: User) -> str:
    row = db.get(Setting, (user.id, "owner_name"))
    return (row.value if row else None) or ""


@router.get("/{scope}")
def export(
    scope: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    images: bool = Query(True, description="embed cover art"),
):
    """Your collection as one file you can send somebody.

    Authenticated like everything else: this builds *your* export, and the
    sharing happens afterwards when you send the file. Nothing here is a
    public URL.

    Returned as a download rather than a page — the browser would happily
    render a megabyte of base64, and then you would have to work out how to
    save the thing you actually wanted.
    """
    if scope not in SPECS and scope != "pokedex":
        raise HTTPException(404, f"nothing to share called {scope!r}")

    owner = _owner_name(db, user)
    if scope == "pokedex":
        dex = cards.pokedex(db=db, user=user)
        entries = dex["entries"] if isinstance(dex, dict) else dex
        body, failed = build_pokedex(entries, owner, with_images=images)
    else:
        body, failed = build_collection(
            scope, everything(scope, db, user), owner, with_images=images
        )

    stamp = f"{date.today():%Y-%m-%d}"
    name = f"yourloot-{scope}-{stamp}.html"
    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            # so the page can say "6 pictures could not be fetched" instead of
            # handing over a patchy file without mentioning it
            "X-Share-Images-Failed": str(failed),
            "Access-Control-Expose-Headers": "X-Share-Images-Failed",
        },
    )


@router.get("")
def shareable(user: User = Depends(current_user)):
    """What can be exported, for the Settings list."""
    return {"scopes": [{"scope": s, "label": TITLES[s]} for s in [*SPECS, "pokedex"]]}
