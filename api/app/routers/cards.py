import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

import httpx

from app import arthash, prices as price_check
from app.binder_view import species_names
from app.cards_util import classify_layer
from app.auth import current_user
from app.db import get_db
from app.limits import dex_ceiling
from app.integrations.tcgdex import tcgdex_client
from app import binders
from app.models import (
    BinderSlot, CardAttrs, CollectionItem, Module, Owned, User, Wanted,
)
from app.ratelimit import outbound
from app.tagging import tagged, tags_for, tags_of
from app.tenancy import guard_entry_write, my_copies, my_want, on_my_shelf, visible
from app.schemas.cards import (
    CardCreate, CardListOut, CardOut, CardScanOut, CardUpdate,
    PriceCheckIn, PriceCheckOut,
)
from app.search import contains, starts_with
from app.sorting import leading_number, rarity_rank

router = APIRouter(prefix="/api/cards", tags=["cards"])


MAX_DEX = 1025  # current national dex (through Scarlet & Violet)
# A frame from a phone camera is a few hundred kilobytes. The cap is here
# so a scan cannot be used to push a file at the server: nothing is stored,
# but it is still read into memory to be fingerprinted.
MAX_SCAN_BYTES = 8 * 1024 * 1024


def card_to_out(item: CollectionItem, uid: int, tags=()) -> CardOut:
    return CardOut(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        source=item.source,
        attrs=item.card_attrs,
        owned=my_copies(item, uid),
        wanted=my_want(item, uid),
        # passed in, not looked up: one query for the page beats one per row
        tags=list(tags),
    )


def _base_query():
    return (
        select(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.cards.value)
        .options(
            joinedload(CollectionItem.card_attrs),
            selectinload(CollectionItem.owned),
            joinedload(CollectionItem.wanted),
        )
    )


@router.get("/search", response_model=CardListOut)
def search_cards(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    name: str = Query(min_length=2),
    number: str | None = None,
    set: str | None = None,
    language: str | None = Query(None, pattern="^(en|ja)$"),
    limit: int = Query(40, le=100),
):
    """Find a physical card by name; the printed number ("91/108", which also
    matches the set size) and set name narrow it to the exact card."""
    # Either the name printed on the card, or the English species name a
    # card printed in another language borrows from its dex number — so
    # "Charizard" finds リザードン, which is otherwise findable only by
    # somebody who can type it.
    term = name.strip()
    q = _base_query().where(
        or_(
            contains(CollectionItem.title, term),
            contains(CardAttrs.name_en, term),
        )
    )
    # Asking for one language is the only way to see past the other. Forty
    # results over a catalogue holding both means whichever sorts first fills
    # the page — English does, deliberately, and this is how somebody looking
    # for the Japanese printing says so.
    if language:
        q = q.where(CardAttrs.language == language)
    total = None
    if number and number.strip():
        # Most cards print "91/108", but subset cards carry their prefix on
        # BOTH halves — "GG07/GG70", "TG03/TG30" — so neither side is reliably
        # digits and the denominator can't be parsed as a plain int.
        m = re.match(r"^\s*([\w-]+)\s*(?:/\s*([\w-]+))?\s*$", number)
        num = (m.group(1) if m else number).strip()
        denominator = (m.group(2) or "") if m else ""
        # Only a plain-digit denominator is the set size. A prefixed one is the
        # SUBSET size, which the dump records inconsistently — Galarian Gallery
        # stores 70 to match "GG70", but Radiant Collection stores its parent
        # set's 113 while the card prints "RC25". Filtering on that would hide
        # the card, and the prefixed numerator is specific enough without it.
        total = int(denominator) if denominator.isdigit() else None
        # numbers are strings ("4", "091", "TG12") — match ignoring leading
        # zeros, and case-insensitively so "gg07" finds "GG07"
        stripped = num.lstrip("0") or num
        q = q.where(
            func.upper(func.ltrim(CardAttrs.card_number, "0")) == stripped.upper()
        )
    if total:
        q = q.where(CardAttrs.set_total == total)
    if set:
        s = set.strip()
        # match the set name, the code printed on modern cards (MEW, JTG),
        # or the dump's internal set id (sv3pt5) as a last resort
        q = q.where(
            or_(
                contains(CardAttrs.set_name, s),
                func.upper(CardAttrs.set_abbr) == s.upper(),
                func.lower(CardAttrs.set_code) == s.lower(),
            )
        )

    items = (
        db.scalars(
            q.order_by(
                # English first. Not a judgement about Japanese cards — a
                # limit of forty and thirteen thousand Japanese printings
                # meant "Charizard" returned thirty-nine of them and one
                # English card, so the language nobody asked about pushed the
                # one they did ask about off the end. Sorting by set code
                # alone did it, because JA set codes are upper case and
                # sort first.
                CardAttrs.language != "en",
                # Then the ones you can recognise. Four in ten Japanese cards
                # have no artwork, and a card with no picture and a title you
                # cannot read is one you can only pick by its number — so the
                # illustrated ones come first rather than scattered among
                # forty rows of empty frames.
                CollectionItem.image_url.is_(None),
                CardAttrs.set_code,
                CollectionItem.title,
            ).limit(limit)
        )
        .unique()
        .all()
    )
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return CardListOut(
        total=len(items),
        items=[card_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.post("/scan", response_model=CardScanOut)
async def scan_card(
    file: UploadFile = File(...),
    limit: int = Query(8, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Which card is this a photograph of?

    A frame from the camera, fingerprinted the same way the catalogue was
    (app/arthash.py) and ranked against it by how many of the sixty-four bits
    disagree. No network, no key, no quota — the answer is already in the
    database, which makes this the only lookup here that costs nothing.

    It returns a short list rather than an answer, and that is the design
    rather than a hedge. A fingerprint sees artwork, so it cannot separate a
    reverse holo from the normal print, or an English card from the Japanese
    one that shares its picture. Those are different rows and the person
    holding the card can see which they have; a scanner that picked for them
    would be confidently wrong about one card in three.

    `sure` is the other half of the answer: true only when the best match is
    close enough that it cannot reasonably be the wrong card, which is the
    only case the camera is allowed to decide on its own. A list that comes
    back unsure is still a good list — it just wants a person to look at it.

    Empty means nothing came close — a card whose art the catalogue never
    had, a photo of the back, a thumb over the frame. The add form's own
    search is still right there.
    """
    raw = await file.read(MAX_SCAN_BYTES + 1)
    if len(raw) > MAX_SCAN_BYTES:
        raise HTTPException(413, "that image is too large to scan")
    if not raw:
        raise HTTPException(400, "no image to scan")

    probes = arthash.variants(raw)
    if not probes:
        raise HTTPException(400, "that file is not an image this can read")

    # A photograph is hashed a dozen ways — straight on, nudged, tilted —
    # and each card is scored by its best agreement with any of them, which
    # is what forgives the hand that held the card a little wrong. That
    # many-to-many comparison is why this happens in Python now rather than
    # as one SQL expression: the whole catalogue's fingerprints are 160KB,
    # and half a million XOR-and-count operations cost less than the JPEG
    # decode that preceded them.
    mask = (1 << arthash.BITS) - 1
    rows = db.execute(
        select(CardAttrs.item_id, CardAttrs.art_hash, CardAttrs.language != "en")
        .join(CollectionItem, CollectionItem.id == CardAttrs.item_id)
        .where(
            CollectionItem.module == Module.cards.value,
            CardAttrs.art_hash.is_not(None),
        )
    ).all()
    near = []
    for item_id, stored, foreign in rows:
        h = stored & mask
        d = min((h ^ p).bit_count() for p in probes)
        if d <= arthash.NEAR:
            near.append((d, foreign, item_id))
    near.sort()
    keep = [item_id for _d, _f, item_id in near[:limit]]
    # Whether the scanner may act on this by itself. The list below is the
    # generous answer for a person to choose from; this is the strict one.
    sure = bool(near) and near[0][0] <= arthash.SURE

    items = []
    if keep:
        by_id = {
            i.id: i
            for i in db.scalars(
                _base_query().where(CollectionItem.id.in_(keep))
            ).unique()
        }
        items = [by_id[k] for k in keep if k in by_id]
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return CardScanOut(
        total=len(items),
        sure=sure,
        items=[card_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.get("/sets")
def list_sets(db: Session = Depends(get_db),
    user: User = Depends(current_user), q: str | None = None):
    """Every set in the card database, newest first — powers the set
    autocomplete so the printed codes are discoverable, and makes a missing
    reseed obvious (abbr shows null)."""
    # Language rides along so the add flow can leave the Japanese sets out
    # until somebody asks for them. Grouping by it is free: a set code belongs
    # to one language — SV1a was never printed in English and sv3pt5 was never
    # printed in Japanese — so this splits no set in two.
    stmt = select(
        CardAttrs.set_code,
        CardAttrs.set_name,
        CardAttrs.set_abbr,
        CardAttrs.set_year,
        func.max(CardAttrs.set_total),
        CardAttrs.language,
    ).group_by(
        CardAttrs.set_code, CardAttrs.set_name, CardAttrs.set_abbr,
        CardAttrs.set_year, CardAttrs.language,
    )
    if q:
        s = q.strip()
        stmt = stmt.where(
            or_(
                contains(CardAttrs.set_name, s),
                starts_with(CardAttrs.set_abbr, s),
                starts_with(CardAttrs.set_code, s),
            )
        )
    rows = db.execute(
        stmt.order_by(CardAttrs.set_year.desc().nulls_last(), CardAttrs.set_name)
    ).all()
    return [
        {"code": c, "name": n, "abbr": a, "year": y, "total": t, "language": lang}
        for c, n, a, y, t, lang in rows
    ]


@router.get("/facets")
def card_facets(db: Session = Depends(get_db),
    user: User = Depends(current_user), include_binder: bool = False):
    """Sets and rarities present among OWNED cards, with counts — drives the
    collection filter dropdowns. Mirrors the list's binder-hiding default."""
    owned_q = select(Owned.id).where(
        Owned.item_id == CardAttrs.item_id, Owned.user_id == user.id
    )
    if not include_binder:
        owned_q = owned_q.where(~binders.filed_anywhere())
    owned_exists = owned_q.exists()
    sets = [
        {"code": c, "name": n, "count": cnt}
        for c, n, cnt in db.execute(
            select(CardAttrs.set_code, CardAttrs.set_name, func.count())
            .where(owned_exists)
            .group_by(CardAttrs.set_code, CardAttrs.set_name)
            .order_by(CardAttrs.set_name)
        )
    ]
    rarities = [
        {"rarity": r, "count": cnt}
        for r, cnt in db.execute(
            select(CardAttrs.rarity, func.count())
            .where(owned_exists, CardAttrs.rarity.is_not(None))
            .group_by(CardAttrs.rarity)
            .order_by(CardAttrs.rarity)
        )
    ]
    return {"sets": sets, "rarities": rarities}


@router.get("", response_model=CardListOut)
def list_cards(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = None,
    set_code: str | None = None,
    rarity: str | None = None,
    dex_no: int | None = None,
    collection: bool = True,
    include_binder: bool = False,
    tag: str | None = None,
    sort: str = Query("dex", pattern="^(dex|title|set|number|rarity|added|oldest)$"),
    limit: int = Query(120, le=300),
    offset: int = 0,
):
    """The card collection: owned cards by default (collection=false browses
    the full catalog, mostly for debugging). Binder-only cards are hidden
    unless include_binder — the binder is its own view."""
    q = _base_query()
    count_q = (
        select(func.count())
        .select_from(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(CollectionItem.module == Module.cards.value)
    )
    # Rows somebody imported and nobody else agreed to stay with them. First
    # in the list because it is not a filter the caller asked for — it is the
    # boundary the rest of the query runs inside.
    filters = [visible(user.id)]
    if search:
        filters.append(contains(CollectionItem.title, search))
    if set_code:
        filters.append(CardAttrs.set_code == set_code)
    if rarity:
        filters.append(CardAttrs.rarity == rarity)
    if dex_no is not None:
        # every card of one Pokémon — what the Pokédex offers as replacements
        filters.append(CardAttrs.national_dex_no == dex_no)
    if tag:
        filters.append(tagged(user.id, "cards", tag, CollectionItem.id))
    if collection:
        owned_q = select(Owned.id).where(
            Owned.item_id == CollectionItem.id, Owned.user_id == user.id
        )
        if not include_binder:
            owned_q = owned_q.where(~binders.filed_anywhere())
        filters.append(owned_q.exists())
    if filters:
        q = q.where(*filters)
        count_q = count_q.where(*filters)

    # card_number is text: promos run "SWSH284", secrets run past the set
    # total, and plenty carry a letter. Sort on the number it starts with so
    # #9 files before #10, and let the text settle the ties.
    by_number = [
        leading_number(CardAttrs.card_number).asc().nulls_last(),
        CardAttrs.card_number.asc().nulls_last(),
    ]
    # Cards are the one collection with a pre-seeded catalog, so
    # CollectionItem.created_at is when the dump was loaded — the same instant
    # for 20,000 rows, and nothing to do with you. When you got the card is on
    # the copy.
    def acquired(agg):
        return (
            select(agg(Owned.created_at))
            .where(Owned.item_id == CollectionItem.id, Owned.user_id == user.id)
            .correlate(CollectionItem)
            .scalar_subquery()
        )

    if sort == "added":
        order = [acquired(func.max).desc().nulls_last(), CollectionItem.id.desc()]
    elif sort == "oldest":
        # the first copy you got, not the most recent — otherwise a second copy
        # of an old card would drag it to the end of "first added"
        order = [acquired(func.min).asc().nulls_last(), CollectionItem.id.asc()]
    elif sort == "title":
        order = [CollectionItem.title, *by_number]
    elif sort == "set":
        # newest set first, and in card order within it — the way a set binder
        # is laid out
        order = [CardAttrs.set_year.desc().nulls_last(), CardAttrs.set_name, *by_number]
    elif sort == "number":
        order = [*by_number, CollectionItem.title]
    elif sort == "rarity":
        order = [rarity_rank(CardAttrs.rarity).desc(), CollectionItem.title]
    else:
        order = [CardAttrs.national_dex_no.asc().nulls_last(), CollectionItem.title]

    total = db.scalar(count_q) or 0
    items = (
        db.scalars(q.order_by(*order).limit(limit).offset(offset)).unique().all()
    )
    tag_map = tags_for(db, user.id, [i.id for i in items])
    return CardListOut(
        total=total,
        items=[card_to_out(i, user.id, tag_map.get(i.id, ())) for i in items],
    )


@router.get("/tcgdex/search", dependencies=[Depends(outbound)])
def tcgdex_search(name: str | None = None,
    set: str | None = None,
    number: str | None = None, user: User = Depends(current_user)):
    """Look the card up in TCGdex — the open catalog that carries cards our
    offline dump lacks (new promo sets, and later additions to ongoing promo
    sets). Needs a name, or a set plus number."""
    if not (name or "").strip() and not (set or "").strip():
        raise HTTPException(400, "give a card name, or a set and number")
    try:
        results = tcgdex_client.search_cards(name=name, set_id=set, number=number)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return []
        raise HTTPException(502, f"TCGdex error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TCGdex unreachable: {e}")
    return results


@router.post("/tcgdex/{card_id}", response_model=CardOut, status_code=201,
             dependencies=[Depends(outbound)])
def add_from_tcgdex(card_id: str, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Import a TCGdex card into the local catalog. Keyed on
    (source='tcgdex', external_id) so re-importing returns the same row and a
    dump reseed can never clobber it."""
    existing = db.scalar(
        select(CollectionItem).where(
            CollectionItem.source == "tcgdex", CollectionItem.external_id == card_id
        )
    )
    if existing:
        return card_to_out(existing, user.id)
    try:
        d = tcgdex_client.get_card(card_id)
    except httpx.HTTPStatusError:
        raise HTTPException(404, "card not found in TCGdex")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"TCGdex unreachable: {e}")

    item = CollectionItem(
        module=Module.cards.value,
        source="tcgdex",
        external_id=card_id,
        title=d["title"],
        image_url=d["image_url"],
        card_attrs=CardAttrs(
            set_code=d["set_id"],
            set_name=d["set_name"],
            set_abbr=(d["set_id"] or "").upper()[:10] or None,
            card_number=d["card_number"],
            set_total=d["set_total"],
            rarity=d["rarity"],
            national_dex_no=d["national_dex_no"],
            layer=classify_layer(d["rarity"]),
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return card_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.post("/prices", response_model=PriceCheckOut,
             dependencies=[Depends(outbound)])
def price_check_page(body: PriceCheckIn, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """What the cards on a binder page go for right now.

    Live from TCGdex and kept nowhere — see prices.py for why. Forty cards at
    most, which is a two-page spread with room to spare; the cap is what
    stops this being a way to price the whole catalogue one request at a
    time. Cards this person cannot see are simply left out of the answer.
    """
    rows = db.scalars(
        select(CollectionItem)
        .where(
            CollectionItem.module == Module.cards.value,
            CollectionItem.id.in_(set(body.item_ids)),
            visible(user.id),
        )
        .options(joinedload(CollectionItem.card_attrs))
    ).unique().all()
    if not rows:
        return PriceCheckOut(prices={}, priced=0, asked=0)
    return PriceCheckOut(**price_check.check(rows, body.variants))


@router.post("", response_model=CardOut, status_code=201)
def create_card(body: CardCreate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Add a card the dump doesn't have yet. A later reseed can't clobber it:
    upserts key on (source='ptcg', external_id) and these are source='manual'."""
    item = CollectionItem(
        module=Module.cards.value,
        source="manual",
        title=body.title.strip(),
        image_url=body.image_url,
        card_attrs=CardAttrs(
            language=body.language,
            set_name=body.set_name,
            set_abbr=body.set_abbr.upper() if body.set_abbr else None,
            set_code=None,
            card_number=body.card_number,
            set_total=body.set_total,
            set_year=body.set_year,
            rarity=body.rarity,
            national_dex_no=body.national_dex_no,
            layer=classify_layer(body.rarity),
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return card_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.patch("/{item_id}", response_model=CardOut)
def update_card(item_id: int, body: CardUpdate, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Edit a manual card (including its photo). Dump-sourced rows are
    read-only — a reseed would overwrite any edit anyway."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.cards.value:
        raise HTTPException(404, "card not found")
    data = body.model_dump(exclude_unset=True)
    # dump rows get their fields rewritten by every reseed, so only the image
    # may be overridden there — the seeder preserves locally-stored images.
    # Manual and TCGdex rows are yours to correct entirely.
    if item.source not in ("manual", "tcgdex") and set(data) - {"image_url"}:
        raise HTTPException(
            400, "only the image can be changed on cards from the card database"
        )
    guard_entry_write(db, item, user)
    if "title" in data:
        item.title = data["title"].strip()
    if "image_url" in data:
        item.image_url = data["image_url"]
        # A fingerprint describes a picture; this row now has a different
        # one. Cleared rather than recomputed here — the pass that fills
        # these in (arthash_run) picks it up on its next run, and a PATCH
        # should not stall on fetching an image.
        item.card_attrs.art_hash = None
    for field in (
        "set_name", "set_abbr", "card_number", "set_total", "set_year",
        "rarity", "national_dex_no",
    ):
        if field in data:
            val = data[field]
            if field == "set_abbr" and val:
                val = val.upper()
            setattr(item.card_attrs, field, val)
    if "rarity" in data:
        item.card_attrs.layer = classify_layer(data["rarity"])
    db.commit()
    db.refresh(item)
    return card_to_out(item, user.id, tags_of(db, user.id, item.id))


@router.delete("/{item_id}", status_code=204)
def delete_card(item_id: int, db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """Only manual entries can be deleted — dump-sourced catalog rows stay
    (removing your copies is what takes a card out of the collection)."""
    item = db.get(CollectionItem, item_id)
    if not item or item.module != Module.cards.value:
        raise HTTPException(404, "card not found")
    if item.source not in ("manual", "tcgdex"):
        raise HTTPException(
            400,
            "cards from the offline dump can't be deleted; remove your copies instead",
        )
    guard_entry_write(db, item, user, deleting=True)
    db.delete(item)
    db.commit()


class HappyUpdate(BaseModel):
    happy: bool


@router.put("/pokedex/{dex_no}/happy")
def set_happy(
    dex_no: int,
    body: HappyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """'Happy with it' — this dex slot's keeper card stays even without an
    IR/SIR, so the binder stops flagging it for upgrade."""
    binders.set_happy(db, binders.dex_binder(db, user.id), str(dex_no), body.happy)
    db.commit()
    return {"dex_no": dex_no, "happy": body.happy}


@router.get("/pokedex")
def pokedex(db: Session = Depends(get_db),
    user: User = Depends(current_user)):
    """The binder: one entry per national dex number, ONE occupant each (the
    copy filed in that slot). `final` = this is the desired card for that
    Pokémon; otherwise it's a placeholder awaiting an upgrade."""
    shelf = binders.dex_binder(db, user.id)
    owned_cards = (
        db.scalars(
            _base_query().where(
                CardAttrs.national_dex_no.is_not(None),
                select(Owned.id)
                .join(BinderSlot, BinderSlot.owned_id == Owned.id)
                .where(
                    Owned.item_id == CollectionItem.id,
                    Owned.user_id == user.id,
                    BinderSlot.binder_id == shelf.id,
                )
                .exists(),
            )
        )
        .unique()
        .all()
    )

    # normally one binder card per dex (enforced on write); for legacy
    # multiples prefer the fancier card, then the newest
    def rank(item):
        a = item.card_attrs
        r = (a.rarity or "").lower()
        return (a.layer or 1, 1 if "special" in r else 0, item.id)

    slots: dict[int, CollectionItem] = {}
    for it in owned_cards:
        dex = it.card_attrs.national_dex_no
        if dex is None or dex > MAX_DEX:
            continue
        if dex not in slots or rank(it) > rank(slots[dex]):
            slots[dex] = it

    names = species_names(db, MAX_DEX)

    final = {
        int(k)
        for (k,) in db.execute(
            select(BinderSlot.slot_key).where(
                BinderSlot.binder_id == shelf.id, BinderSlot.happy
            )
        )
        if k and k.isdigit()
    }

    def card_out(item):
        if item is None:
            return None
        a = item.card_attrs
        binder_copy = next(
            (o for o in item.owned
             if any(sl.binder_id == shelf.id for sl in o.binder_slots)),
            None,
        )
        return {
            "id": item.id,
            # the binder copy itself, so the UI can pull it out of the binder
            "owned_id": binder_copy.id if binder_copy else None,
            "title": item.title,
            "image_url": item.image_url,
            "set_name": a.set_name,
            "set_abbr": a.set_abbr,
            "set_total": a.set_total,
            "set_year": a.set_year,
            "card_number": a.card_number,
            "rarity": a.rarity,
            "layer": a.layer or 1,
            # print details of the copy actually sleeved in the binder
            "variant": binder_copy.variant if binder_copy else None,
            "stamp": binder_copy.stamp if binder_copy else None,
            "condition": binder_copy.condition if binder_copy else None,
            "grader": binder_copy.grader if binder_copy else None,
            "grade": binder_copy.grade if binder_copy else None,
        }

    # How far the binder runs. There are two Pokédex builders in this
    # codebase — this one and binder_view._dex_entries — and capping only one
    # of them is exactly the bug this comment exists to prevent: the app asks
    # this route, so a limit applied only to the other one does nothing at
    # all while looking like it works.
    ceiling = dex_ceiling(user)
    entries = []
    for dex in range(1, ceiling + 1):
        entries.append({
            "dex_no": dex,
            "name": names.get(dex),
            "card": card_out(slots.get(dex)),
            "final": dex in final,
        })
    # max_dex is what this person's binder holds, not what the Pokédex has —
    # the UI counts pages from it.
    #
    # The shape rides along because this page and /binders/<the dex one> draw
    # the same Pokédex, and fetching it separately here would let the two
    # disagree for as long as one request was in flight.
    return {
        "max_dex": ceiling,
        "binder": {
            "id": shelf.id,
            "rows": shelf.rows,
            "cols": shelf.cols,
            "double_page": shelf.double_page,
            "allow_ja": shelf.allow_ja,
            "color": shelf.color,
        },
        "entries": entries,
    }
