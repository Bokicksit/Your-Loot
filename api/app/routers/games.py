import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import current_user
from app.db import get_db
from app.integrations import libretro
from app.integrations.igdb import igdb_client
from app.models import CollectionItem, GameAttrs, Module, Owned, Platform, Wanted, User
from app.ratelimit import outbound
from app.tagging import tagged, tags_for, tags_of
from app.tenancy import guard_entry_write, my_copies, my_want, on_my_shelf, visible
from app.schemas.games import GameAttrsOut, GameCreate, GameListOut, GameOut, GameUpdate
from app.search import contains
from app.sorting import year_from_title

router = APIRouter(prefix="/api/games", tags=["games"])


def game_to_out(item: CollectionItem, uid: int, tags=()) -> GameOut:
    a = item.game_attrs
    return GameOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        notes=item.notes,
        attrs=GameAttrsOut(
            igdb_slug=a.igdb_slug,
            hardware_kind=a.hardware_kind,
            platform_id=a.platform_id,
            platform_name=a.platform.name if a.platform else None,
            platform_abbr=a.platform.abbreviation if a.platform else None,
            region=a.region,
            is_hardware=a.is_hardware,
            summary=a.summary,
            release_year=a.release_year,
            genres=a.genres,
            developer=a.developer,
            publisher=a.publisher,
            model_number=a.model_number,
            serial_number=a.serial_number,
            working=a.working,
            parent_id=a.parent_id,
        ),
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        # passed in, not looked up: one query for the page beats one per row
        tags=list(tags),
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(GameAttrs, GameAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.games.value)
        .options(
            joinedload(CollectionItem.game_attrs).joinedload(GameAttrs.platform),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/boxart", dependencies=[Depends(outbound)])
def game_boxart(
    title: str,
    platform_id: int | None = None,
    region: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """A scan of the actual box, from libretro-thumbnails.

    Needs no key and covers NES through Xbox 360. Returns `{"url": null}`
    rather than a 404 when there's no scan, because "we looked and there
    isn't one" is a normal answer here, not a failure.
    """
    abbr = None
    if platform_id is not None:
        platform = db.get(Platform, platform_id)
        abbr = platform.abbreviation if platform else None
    if not libretro.supported(abbr):
        return {"url": None, "supported": False}
    return {"url": libretro.boxart(title, abbr, region), "supported": True}


@router.get("/platforms")
def list_platforms(db: Session = Depends(get_db),
    user: User = Depends(current_user), in_use: bool = False):
    """Full lookup for the add form; in_use=true returns only platforms that
    have at least one collection entry (with counts) — used by the filter UI."""
    if in_use:
        # mirror the library view: wanted-only entries don't count here either
        _shelf = on_my_shelf(user.id, GameAttrs.item_id)
        rows = db.execute(
            select(Platform, func.count(GameAttrs.item_id))
            .join(GameAttrs, GameAttrs.platform_id == Platform.id)
            .where(_shelf)
            .group_by(Platform.id)
            .order_by(Platform.name)
        ).all()
        return [
            {"id": p.id, "name": p.name, "abbreviation": p.abbreviation, "count": c}
            for p, c in rows
        ]
    rows = db.scalars(select(Platform).order_by(Platform.name)).all()
    return [{"id": p.id, "name": p.name, "abbreviation": p.abbreviation} for p in rows]


@router.get("/hardware/catalogue")
def hardware_catalogue(
    q: str | None = None,
    kind: str | None = Query(None, pattern="^(console|controller|accessory)$"),
    limit: int = Query(60, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """The seeded NA console-variant catalogue, for pick-to-prefill.

    Template rows (source="yourloot", from seed_consoles.py) that nobody
    owns — picking one prefills the add form and the user's submit creates
    their own row, because serial number and working state belong to the
    unit on their shelf, not to the catalogue. Keyless and instant, like the
    card and amiibo catalogues: the whole dataset lives in this database.
    """
    filters = [
        CollectionItem.source == "yourloot",
        GameAttrs.is_hardware.is_(True),
        visible(user.id),
    ]
    if q and q.strip():
        term = q.strip()
        filters.append(
            contains(CollectionItem.title, term)
            | contains(GameAttrs.model_number, term)
            | GameAttrs.platform.has(contains(Platform.name, term))
        )
    if kind:
        filters.append(GameAttrs.hardware_kind == kind)

    items = db.scalars(
        _base_query()
        .where(*filters)
        .order_by(
            GameAttrs.release_year.asc().nulls_last(), CollectionItem.title
        )
        .limit(limit)
    ).unique().all()
    return {
        "items": [game_to_out(i, user.id) for i in items],
        "seeded": bool(
            db.scalar(
                select(CollectionItem.id)
                .where(
                    CollectionItem.module == Module.games.value,
                    CollectionItem.source == "yourloot",
                )
                .limit(1)
            )
        ),
    }


@router.get("/igdb/search", dependencies=[Depends(outbound)])
def igdb_search(q: str = Query(min_length=2), user: User = Depends(current_user)):
    if not igdb_client.configured:
        raise HTTPException(
            503, "IGDB not configured — set IGDB_CLIENT_ID / IGDB_CLIENT_SECRET"
        )
    try:
        return igdb_client.search_games(q)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"IGDB error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"IGDB unreachable: {e}")


@router.get("", response_model=GameListOut)
def list_games(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = None,
    platform_id: int | None = None,
    is_hardware: bool | None = None,
    hardware_kind: str | None = None,
    tag: str | None = None,
    sort: str = Query("title", pattern="^(title|platform|year|added|oldest)$"),
    include_wanted_only: bool = False,
    limit: int = Query(100, le=200),
    offset: int = 0,
):
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(GameAttrs, GameAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.games.value)
    )
    # Rows somebody imported and nobody else agreed to stay with them. First
    # in the list because it is not a filter the caller asked for — it is the
    # boundary the rest of the query runs inside.
    filters = [visible(user.id)]
    if search:
        filters.append(contains(CollectionItem.title, search))
    if platform_id is not None:
        filters.append(GameAttrs.platform_id == platform_id)
    if is_hardware is not None:
        filters.append(GameAttrs.is_hardware == is_hardware)
    if hardware_kind is not None:
        # "unsorted" is a real answer — every row made before kinds existed
        filters.append(
            GameAttrs.hardware_kind.is_(None)
            if hardware_kind == "unsorted"
            else GameAttrs.hardware_kind == hardware_kind
        )
    # A shelf is what you own; the Wanted tab is where a wish lives. Asking
    if tag:
        filters.append(tagged(user.id, ("hardware" if is_hardware else "games"), tag, CollectionItem.id))
    # for both is what include_wanted_only means.
    filters.append(on_my_shelf(user.id, CollectionItem.id, include_wanted_only))

    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    if sort == "added":
        order = [CollectionItem.created_at.desc(), CollectionItem.id.desc()]
    elif sort == "oldest":
        order = [CollectionItem.created_at.asc(), CollectionItem.id.asc()]
    elif sort == "platform":
        q = q.outerjoin(Platform, GameAttrs.platform_id == Platform.id)
        order = [Platform.name.asc().nulls_last(), CollectionItem.title]
    elif sort == "year":
        # IGDB rarely fills release_year, but the title it hands back carries
        # the year in brackets, so fall through to that before giving up
        year = func.coalesce(GameAttrs.release_year, year_from_title(CollectionItem.title))
        order = [year.desc().nulls_last(), CollectionItem.title]
    else:
        order = [CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    )
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return GameListOut(
        total=total,
        items=[game_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.post("", response_model=GameOut, status_code=201)
def create_game(body: GameCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Manual entry, or IGDB-prefilled when igdb_id is set (dedupes on it)."""
    if body.platform_id is not None and db.get(Platform, body.platform_id) is None:
        raise HTTPException(400, "unknown platform_id")
    if body.igdb_id is not None:
        existing = db.scalar(
            select(CollectionItem).where(
                CollectionItem.source == "igdb",
                CollectionItem.external_id == str(body.igdb_id),
            )
        )
        if existing:
            # Hand back the row that is already there rather than refusing.
            # This used to be a 409, which read as "you have this" but asked
            # the catalogue, not you — and the catalogue is deliberately shared.
            # So it fired when somebody else owned the game, and it kept firing
            # after you deleted your own copy, because deleting a copy leaves
            # the catalogue entry standing.
            #
            # UNIQUE(source, external_id) means there can only ever be one row
            # for an IGDB id, which is the point: one catalogue entry, a copy
            # each. The caller adds its owned record to whatever comes back, so
            # returning this gets a second copy, a re-add after a delete, and a
            # second person's first copy all right by doing nothing special.
            return game_to_out(existing, user.id, tags_of(db, user.id, existing.id))
    item = CollectionItem(
        module=Module.games.value,
        source="igdb" if body.igdb_id is not None else "manual",
        external_id=str(body.igdb_id) if body.igdb_id is not None else None,
        title=body.title,
        image_url=body.image_url,
        notes=body.notes,
        game_attrs=GameAttrs(
            igdb_slug=body.igdb_slug,
            hardware_kind=body.hardware_kind if body.is_hardware else None,
            platform_id=body.platform_id,
            region=body.region,
            is_hardware=body.is_hardware,
            summary=body.summary,
            release_year=body.release_year,
            genres=body.genres,
            developer=body.developer,
            publisher=body.publisher,
            model_number=body.model_number,
            serial_number=body.serial_number,
            working=body.working,
            parent_id=body.parent_id,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return game_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.patch("/{item_id}", response_model=GameOut)
def update_game(item_id: int, body: GameUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.games.value:
        raise HTTPException(404, "game not found")
    if item.source == "yourloot":
        # Templates prefill everybody's add form; your own row is the one
        # that takes a serial number. Nothing in the UI edits these — this
        # catches a mistake, not a workflow.
        raise HTTPException(409, "that is a catalogue entry — add it to edit your own")
    guard_entry_write(db, item, user)
    data = body.model_dump(exclude_unset=True)
    if "platform_id" in data and data["platform_id"] is not None:
        if db.get(Platform, data["platform_id"]) is None:
            raise HTTPException(400, "unknown platform_id")
    for field in ("title", "image_url", "notes"):
        if field in data:
            setattr(item, field, data[field])
    for field in (
        "platform_id", "region", "is_hardware", "hardware_kind",
        "model_number", "serial_number", "working", "parent_id",
    ):
        if field in data:
            setattr(item.game_attrs, field, data[field])
    db.commit()
    db.refresh(item)
    return game_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.delete("/{item_id}", status_code=204)
def delete_game(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Removes the catalog entry AND its owned/wanted records (cascade) —
    meant for fixing manual-entry mistakes, not for 'I sold this'."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.games.value:
        raise HTTPException(404, "game not found")
    if item.source == "yourloot":
        # A catalogue template is everybody's — your own console made from
        # it is a separate row, and that one deletes fine.
        raise HTTPException(409, "that is a catalogue entry — it has no copies to remove")
    guard_entry_write(db, item, user, deleting=True)
    db.delete(item)
    db.commit()
