from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.models import CardAttrs, CollectionItem, GameAttrs, Module, Owned, User, Wanted
from app.tagging import tags_for, tags_of
from app.tenancy import my_copies, my_want, owns
from app.schemas.collection import ItemStatusOut, WantedItemOut
from app.schemas.common import OwnedCreate, WantedCreate

router = APIRouter(prefix="/api", tags=["collection"])


def _get_item(db: Session, item_id: int) -> CollectionItem:
    item = db.get(CollectionItem, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    return item


def _status(db: Session, item: CollectionItem, uid: int) -> ItemStatusOut:
    """Carries the tags as well as the copies. Adding a copy returns this,
    and a client that refreshed its row from a reply with no tags in it would
    blank the labels it was showing a moment ago."""
    return ItemStatusOut(
        item_id=item.id,
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        tags=tags_of(db, uid, item.id),
    )


def _enforce_single_binder(db: Session, item: CollectionItem, keep_owned_id: int, uid: int):
    """A binder holds ONE card per Pokémon: flagging a copy in_binder unflags
    any other binder copy sharing the same dex number (the physical swap)."""
    if item.module != Module.cards.value or not item.card_attrs:
        return
    dex = item.card_attrs.national_dex_no
    if dex is None:
        return
    others = db.scalars(
        select(Owned)
        .join(CollectionItem, CollectionItem.id == Owned.item_id)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            Owned.user_id == uid,
            Owned.in_binder,
            Owned.id != keep_owned_id,
            CardAttrs.national_dex_no == dex,
        )
    ).all()
    for o in others:
        o.in_binder = False


@router.post("/items/{item_id}/owned", response_model=ItemStatusOut)
def add_owned(
    item_id: int,
    body: OwnedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = _get_item(db, item_id)
    owned = Owned(item_id=item.id, user_id=user.id, **body.model_dump())
    db.add(owned)
    if body.in_binder:
        db.flush()
        _enforce_single_binder(db, item, owned.id, user.id)
    db.commit()
    db.refresh(item)
    return _status(db, item, user.id)


@router.patch("/items/{item_id}/owned/{owned_id}", response_model=ItemStatusOut)
def update_owned(
    item_id: int,
    owned_id: int,
    body: OwnedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Edit a copy's condition/completeness/notes — e.g. filling them in after
    a 'Got it' acquisition. Only fields present in the request change."""
    item = _get_item(db, item_id)
    owned = db.get(Owned, owned_id)
    if not owned or owned.item_id != item.id or owned.user_id != user.id:
        raise HTTPException(404, "owned record not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(owned, k, v)
    if data.get("in_binder"):
        _enforce_single_binder(db, item, owned.id, user.id)
    db.commit()
    db.refresh(item)
    return _status(db, item, user.id)


@router.delete("/items/{item_id}/owned/{owned_id}", response_model=ItemStatusOut)
def remove_owned(
    item_id: int,
    owned_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = _get_item(db, item_id)
    owned = db.get(Owned, owned_id)
    # somebody else's copy is not yours to delete, and saying "not found"
    # rather than "not yours" keeps their collection none of your business
    if not owned or owned.item_id != item.id or owned.user_id != user.id:
        raise HTTPException(404, "owned record not found")
    db.delete(owned)
    db.commit()
    db.refresh(item)
    return _status(db, item, user.id)


@router.post("/items/{item_id}/wanted", response_model=ItemStatusOut)
def add_wanted(
    item_id: int,
    body: WantedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = _get_item(db, item_id)
    if my_want(item, user.id) is None:
        db.add(Wanted(item_id=item.id, user_id=user.id, **body.model_dump()))
        db.commit()
        db.refresh(item)
    return _status(db, item, user.id)


@router.delete("/items/{item_id}/wanted", response_model=ItemStatusOut)
def remove_wanted(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = _get_item(db, item_id)
    mine = my_want(item, user.id)
    if mine is not None:
        db.delete(mine)
        # a games/movies entry that was wanted-only existed solely for the
        # wishlist — prune it, or it would surface in the library as an
        # unowned ghost row. Cards are catalog rows and always stay.
        # only prune it if nobody at all is holding it — another person's
        # copy or wish is reason enough for the row to go on existing
        if item.module != Module.cards.value and not item.owned and len(item.wanted) <= 1:
            db.delete(item)
            db.commit()
            return ItemStatusOut(item_id=item_id, owned=[], wanted=None)
        db.commit()
        db.refresh(item)
    return _status(db, item, user.id)


def _detail(item: CollectionItem) -> str:
    """Per-module one-line summary so the wanted list UI stays module-agnostic."""
    if item.module == Module.cards.value and item.card_attrs:
        a = item.card_attrs
        parts = [a.set_name, f"#{a.card_number}" if a.card_number else None, a.variant]
    elif item.module == Module.games.value and item.game_attrs:
        a = item.game_attrs
        parts = [a.platform.name if a.platform else None, a.region,
                 "hardware" if a.is_hardware else None]
    elif item.module == Module.movies.value and item.movie_attrs:
        a = item.movie_attrs
        parts = [a.format, a.edition, a.region_code]
    elif item.module == Module.books.value and item.book_attrs:
        a = item.book_attrs
        parts = [a.author, a.format, a.publish_year]
    elif item.module == Module.records.value and item.record_attrs:
        a = item.record_attrs
        parts = [a.artist, a.format, a.release_year]
    elif item.module == Module.lego.value and item.lego_attrs:
        a = item.lego_attrs
        parts = [a.set_number, a.theme, a.release_year]
    elif item.module == Module.comics.value and item.comic_attrs:
        a = item.comic_attrs
        parts = [a.series, f"#{a.issue_number}" if a.issue_number else None, a.variant]
    else:
        parts = []
    return " · ".join(str(p) for p in parts if p)


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Per-module counts for the home screen tiles. `items` counts only
    titles with at least one owned copy — wanted-only entries belong to the
    Wanted tile, not the collection counts.

    Hardware is reported separately even though it has no module of its own.
    A console and a cartridge share a table because they share a platform, a
    region and a completeness — but they are two tiles on the home screen, and
    the split has to happen somewhere. Here is better than in the client,
    which previously had no hardware number to show and used the games one.
    """
    owned_exists = owns(user.id, CollectionItem.id)
    items = dict(
        db.execute(
            select(CollectionItem.module, func.count())
            .where(owned_exists)
            .group_by(CollectionItem.module)
        ).all()
    )
    owned = dict(
        db.execute(
            select(CollectionItem.module, func.count(Owned.id))
            .join(Owned, Owned.item_id == CollectionItem.id)
            .where(Owned.user_id == user.id)
            .group_by(CollectionItem.module)
        ).all()
    )
    wanted = dict(
        db.execute(
            select(CollectionItem.module, func.count(Wanted.id))
            .join(Wanted, Wanted.item_id == CollectionItem.id)
            .where(Wanted.user_id == user.id)
            .group_by(CollectionItem.module)
        ).all()
    )
    # `module` alone can't tell a console from a game, so ask the attrs table
    # which of the games rows are hardware and subtract them out.
    hw_items, hw_owned, hw_wanted = (
        db.scalar(
            select(func.count(q))
            .select_from(CollectionItem)
            .join(GameAttrs, GameAttrs.item_id == CollectionItem.id)
            .outerjoin(j, j.item_id == CollectionItem.id)
            .where(GameAttrs.is_hardware, cond)
        )
        or 0
        for q, j, cond in (
            (func.distinct(CollectionItem.id), Owned, Owned.user_id == user.id),
            (Owned.id, Owned, Owned.user_id == user.id),
            (Wanted.id, Wanted, Wanted.user_id == user.id),
        )
    )

    out = {
        m.value: {
            "items": items.get(m.value, 0),
            "owned": owned.get(m.value, 0),
            "wanted": wanted.get(m.value, 0),
        }
        for m in Module
    }
    games = out.get(Module.games.value, {"items": 0, "owned": 0, "wanted": 0})
    out["hardware"] = {"items": hw_items, "owned": hw_owned, "wanted": hw_wanted}
    out[Module.games.value] = {
        "items": games["items"] - hw_items,
        "owned": games["owned"] - hw_owned,
        "wanted": games["wanted"] - hw_wanted,
    }
    return out


@router.get("/wanted", response_model=list[WantedItemOut])
def wanted_list(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    module: str | None = None,
    sort: str = Query("added", pattern="^(added|oldest|title|module)$"),
):
    """The unified wanted list — one query across all modules.

    Ordered newest-first by default. `wanted.priority` exists and nothing has
    ever set it, so ordering by it put every row in one undifferentiated NULL
    bucket and fell through to oldest-first — which meant the thing you added
    a minute ago went to the bottom of the list. When priority becomes
    something the UI can actually set, it earns a sort of its own.

    "Added" is when it went on the wanted list, not when the catalogue first
    heard of the item — the date that matters here is the day you decided you
    wanted it.
    """
    q = (
        select(Wanted)
        .join(CollectionItem)
        .where(Wanted.user_id == user.id)
        .options(
            joinedload(Wanted.item).joinedload(CollectionItem.card_attrs),
            joinedload(Wanted.item)
            .joinedload(CollectionItem.game_attrs)
            .joinedload(GameAttrs.platform),
            joinedload(Wanted.item).joinedload(CollectionItem.movie_attrs),
            joinedload(Wanted.item).joinedload(CollectionItem.book_attrs),
            joinedload(Wanted.item).joinedload(CollectionItem.record_attrs),
            joinedload(Wanted.item).joinedload(CollectionItem.lego_attrs),
            joinedload(Wanted.item).joinedload(CollectionItem.comic_attrs),
        )
    )
    if module:
        q = q.where(CollectionItem.module == module)

    if sort == "oldest":
        order = [Wanted.created_at.asc(), Wanted.id.asc()]
    elif sort == "title":
        order = [CollectionItem.title]
    elif sort == "module":
        # grouped by collection, and alphabetical inside each
        order = [CollectionItem.module, CollectionItem.title]
    else:
        order = [Wanted.created_at.desc(), Wanted.id.desc()]
    q = q.order_by(*order)
    def _facet(item: CollectionItem) -> str | None:
        """Sub-filter value: system for games, genre for movies."""
        if item.module == Module.games.value and item.game_attrs and item.game_attrs.platform:
            p = item.game_attrs.platform
            return p.abbreviation or p.name
        if item.module == Module.movies.value and item.movie_attrs:
            return item.movie_attrs.genre
        if item.module == Module.books.value and item.book_attrs:
            return item.book_attrs.author
        if item.module == Module.records.value and item.record_attrs:
            return item.record_attrs.artist
        if item.module == Module.lego.value and item.lego_attrs:
            return item.lego_attrs.theme
        if item.module == Module.comics.value and item.comic_attrs:
            return item.comic_attrs.series
        return None

    def _info(item: CollectionItem) -> tuple[str, str | None]:
        """Expandable row info: (facts line, optional longer text)."""
        parts: list = []
        text = None
        if item.module == Module.cards.value and item.card_attrs:
            a = item.card_attrs
            parts = [a.set_name, a.set_year, a.rarity]
        elif item.module == Module.games.value and item.game_attrs:
            a = item.game_attrs
            parts = [
                a.release_year,
                a.genres,
                a.developer and f"Dev: {a.developer}",
                a.publisher and a.publisher != a.developer and f"Pub: {a.publisher}",
            ]
            text = a.summary
        elif item.module == Module.movies.value and item.movie_attrs:
            a = item.movie_attrs
            parts = [a.genre]
            text = a.overview
        elif item.module == Module.books.value and item.book_attrs:
            a = item.book_attrs
            parts = [
                a.publish_year,
                a.publisher,
                a.page_count and f"{a.page_count} pages",
                a.series,
            ]
            text = a.blurb
        elif item.module == Module.records.value and item.record_attrs:
            a = item.record_attrs
            parts = [
                a.release_year,
                a.label,
                a.catalog_number,
                a.country,
                a.track_count and f"{a.track_count} tracks",
            ]
        elif item.module == Module.lego.value and item.lego_attrs:
            a = item.lego_attrs
            parts = [
                a.set_number,
                a.release_year,
                a.piece_count and f"{a.piece_count} pieces",
                a.minifig_count and f"{a.minifig_count} minifigs",
                a.subtheme,
            ]
        elif item.module == Module.comics.value and item.comic_attrs:
            a = item.comic_attrs
            parts = [
                a.publisher,
                a.volume_year and f"vol. {a.volume_year}",
                a.cover_year,
                a.creators,
            ]
            text = a.blurb
        line = "  ·  ".join(str(p) for p in parts if p)
        return line, text

    def _badge(item: CollectionItem) -> str | None:
        """Left-edge row badge: system for games, media format for movies."""
        if item.module == Module.games.value and item.game_attrs and item.game_attrs.platform:
            p = item.game_attrs.platform
            return p.abbreviation or p.name
        if item.module == Module.movies.value and item.movie_attrs:
            return item.movie_attrs.format
        if item.module == Module.books.value and item.book_attrs:
            return item.book_attrs.format
        if item.module == Module.records.value and item.record_attrs:
            return item.record_attrs.format
        if item.module == Module.lego.value and item.lego_attrs:
            return item.lego_attrs.set_number
        if item.module == Module.comics.value and item.comic_attrs:
            return f"#{item.comic_attrs.issue_number}" if item.comic_attrs.issue_number else None
        return None

    def _ui_module(item: CollectionItem) -> str:
        """Hardware is stored in the games module but is its own collection in
        the UI, so the wanted list can filter it separately."""
        if item.module == Module.games.value and item.game_attrs and item.game_attrs.is_hardware:
            return "hardware"
        return item.module

    rows = db.scalars(q).unique().all()
    tag_map = tags_for(db, user.id, [w.item.id for w in rows])
    out = []
    for w in rows:
        line, text = _info(w.item)
        out.append(
            WantedItemOut(
                tags=tag_map.get(w.item.id, []),
                item_id=w.item.id,
                module=_ui_module(w.item),
                title=w.item.title,
                image_url=w.item.image_url,
                detail=_detail(w.item),
                facet=_facet(w.item),
                badge=_badge(w.item),
                info_line=line,
                info_text=text,
                wanted=w,
            )
        )
    return out


@router.get("/duplicates")
def duplicates(
    module: str,
    title: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Do you already have something by this name in this collection?

    Asked by the add form before it creates anything, so a second copy is a
    decision rather than an accident — two identical rows are easy to make and
    tedious to find again.

    Matched on the title alone, case- and space-insensitively. Deliberately
    looser than the thing that makes two items genuinely distinct: Halo 3 on
    Xbox and on the 360 are different objects, but being asked about them is
    the correct outcome, and a check that only fired on an exact match of
    every field would never fire on the case this exists for.

    Scoped to your own shelf, so a housemate's copy is not an answer to a
    question about yours.
    """
    key = " ".join((title or "").split()).casefold()
    if not key:
        return {"matches": []}

    is_hardware = module == "hardware"
    db_module = Module.games.value if is_hardware else module
    q = (
        select(CollectionItem)
        .where(
            CollectionItem.module == db_module,
            func.lower(func.trim(CollectionItem.title)) == key,
            owns(user.id, CollectionItem.id),
        )
        .options(selectinload(CollectionItem.owned))
    )
    if db_module == Module.games.value:
        # hardware and games share a table and must not answer for each other
        q = q.join(GameAttrs, GameAttrs.item_id == CollectionItem.id).where(
            GameAttrs.is_hardware.is_(is_hardware)
        )

    rows = db.scalars(q).unique().all()
    return {
        "matches": [
            {
                "item_id": i.id,
                "title": i.title,
                "detail": _detail(i),
                "copies": len(my_copies(i, user.id)),
            }
            for i in rows
        ]
    }
