"""The LEGO Pokédex: every Pokémon LEGO has made, and which you have caught.

Mounted under the LEGO router, so it is on and off with LEGO itself.

A capture is a Smart Tag tapped with a phone. Chrome on Android hands the page
the tag's serial number — the Pokémon is in the chip's memory, which the
browser cannot read — so the first tap of a tile asks which Pokémon it is,
and every tap after that captures. Owning the set can count instead, for an
iPhone or anybody without NFC: a switch, off unless asked for.

Pictures are LEGO's, not cards: each Pokémon shows its set's box picture
from Rebrickable until you photograph your own build, which replaces it.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import lego_dex as catalogue
from app.auth import current_user
from app.binder_view import species_names
from app.db import get_db
from app.models import (
    CollectionItem, LegoAttrs, LegoTile, Module, Owned, Setting, User,
)

router = APIRouter(prefix="/pokedex", tags=["lego"])

BY_SETS = "lego_dex_by_sets"
PHOTO = "lego_dex_photo:"   # + dex number — your own photo of the build
# Rebrickable's box picture for a set; the LEGO side already shows these
SET_ART = "https://cdn.rebrickable.com/media/sets/{}-1.jpg"
MAX_DEX = 1025
HEX = re.compile(r"^[0-9a-f]{8,32}$")


class Serial(BaseModel):
    serial: str = Field(min_length=8, max_length=64)


class Pairing(Serial):
    dex_no: int = Field(ge=1, le=MAX_DEX)


class DexSettings(BaseModel):
    by_sets: bool


class DexPhoto(BaseModel):
    image_url: str | None = Field(default=None, max_length=500)


def _serial(raw: str) -> str:
    """`3a:80:82:24:01:5c:16:e0`, `3A-80-…` and `3a8082…` are one tile."""
    s = re.sub(r"[^0-9a-fA-F]", "", raw or "").lower()
    if not HEX.match(s):
        raise HTTPException(422, "that is not a tag serial number")
    return s


def _by_sets(db: Session, user: User) -> bool:
    row = db.get(Setting, (user.id, BY_SETS))
    return bool(row and row.value == "1")


def render(db: Session, user: User) -> dict:
    by_sets = _by_sets(db, user)
    tiles = db.scalars(
        select(LegoTile).where(LegoTile.user_id == user.id).order_by(LegoTile.created_at)
    ).all()

    # the LEGO sets you own, by bare set number, with the picture your copy
    # of the set carries — which may be one you chose over Rebrickable's
    owned_art: dict[str, str | None] = {}
    for n, url in db.execute(
        select(LegoAttrs.set_number, CollectionItem.image_url)
        .join(Owned, Owned.item_id == LegoAttrs.item_id)
        .join(CollectionItem, CollectionItem.id == LegoAttrs.item_id)
        .where(Owned.user_id == user.id)
    ).all():
        key = catalogue.set_key(n)
        owned_art[key] = owned_art.get(key) or url
    owned_sets = set(owned_art)
    photos = {
        int(p.key[len(PHOTO):]): p.value
        for p in db.scalars(
            select(Setting).where(Setting.user_id == user.id, Setting.key.like(PHOTO + "%"))
        ).all()
        if p.value and p.key[len(PHOTO):].isdigit()
    }

    sets_of: dict[int, list[dict]] = {}
    tagged: set[int] = set()
    for number, name, dex, has_tags in catalogue.SETS:
        for n in dex:
            sets_of.setdefault(n, []).append({
                "number": number, "name": name,
                "owned": number in owned_sets, "tags": has_tags,
            })
            if has_tags:
                tagged.add(n)

    # every Pokémon LEGO has made, plus any you paired that the list has not
    # caught up with yet — a new wave should not need a release to be caught
    dex_nos = sorted(set(sets_of) | {t.dex_no for t in tiles})
    names = dict(catalogue.NAMES)
    if any(n not in names for n in dex_nos):
        names = {**species_names(db), **names}

    def set_art(n: int) -> str | None:
        """The box this Pokémon comes in: one you own first, then one with a
        Smart Tag, then any — and your copy's own picture if it has one."""
        sets = sets_of.get(n, [])
        if not sets:
            return None
        best = sorted(sets, key=lambda s: (not s["owned"], not s["tags"]))[0]
        return owned_art.get(best["number"]) or SET_ART.format(best["number"])

    entries = []
    for n in dex_nos:
        mine = [t for t in tiles if t.dex_no == n]
        by_set = by_sets and any(s["owned"] for s in sets_of.get(n, []))
        how = "tile" if mine else ("set" if by_set else None)
        entries.append({
            "dex_no": n,
            "name": names.get(n) or f"#{n:04d}",
            "photo": photos.get(n),
            "set_art": set_art(n),
            "art": photos.get(n) or set_art(n),
            "sets": sets_of.get(n, []),
            "has_tile": n in tagged or bool(mine),
            "captured": how is not None,
            "how": how,
            # never the serial itself: it identifies a physical object, and
            # the page has no use for it beyond being able to forget the tile
            "tiles": [{"id": t.id, "since": t.created_at.isoformat() if t.created_at else None}
                      for t in mine],
        })
    return {
        "by_sets": by_sets,
        "total": len(entries),
        "captured": sum(1 for e in entries if e["captured"]),
        "entries": entries,
    }


@router.get("")
def pokedex(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return render(db, user)


@router.post("/scan")
def scan(body: Serial, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """A tile was tapped. Known: that is a capture. Unknown: the page asks
    which Pokémon it is and pairs it — nothing is written until it does."""
    serial = _serial(body.serial)
    tile = db.scalar(
        select(LegoTile).where(LegoTile.user_id == user.id, LegoTile.serial == serial)
    )
    if tile is None:
        return {"known": False}
    page = render(db, user)
    entry = next(e for e in page["entries"] if e["dex_no"] == tile.dex_no)
    return {"known": True, "dex_no": tile.dex_no, "name": entry["name"], "pokedex": page}


@router.post("/tiles", status_code=201)
def pair(body: Pairing, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """This tile is this Pokémon. Pairing a tile already paired re-answers it,
    which is how a wrong first answer gets put right."""
    serial = _serial(body.serial)
    tile = db.scalar(
        select(LegoTile).where(LegoTile.user_id == user.id, LegoTile.serial == serial)
    )
    if tile is None:
        tile = LegoTile(user_id=user.id, serial=serial, dex_no=body.dex_no)
        db.add(tile)
    else:
        tile.dex_no = body.dex_no
    db.commit()
    page = render(db, user)
    entry = next(e for e in page["entries"] if e["dex_no"] == body.dex_no)
    return {"dex_no": body.dex_no, "name": entry["name"], "pokedex": page}


@router.delete("/tiles/{tile_id}")
def forget(tile_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tile = db.get(LegoTile, tile_id)
    if tile is None or tile.user_id != user.id:
        raise HTTPException(404, "no such tile")
    db.delete(tile)
    db.commit()
    return render(db, user)


@router.put("/{dex_no}/photo")
def photo(
    dex_no: int, body: DexPhoto, db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Your own photo of the build, or none to go back to the box picture."""
    if not 1 <= dex_no <= MAX_DEX:
        raise HTTPException(404, "no such Pokémon")
    key = f"{PHOTO}{dex_no}"
    url = (body.image_url or "").strip()
    row = db.get(Setting, (user.id, key))
    if not url:
        if row is not None:
            db.delete(row)
    else:
        if row is None:
            row = Setting(user_id=user.id, key=key)
            db.add(row)
        row.value = url
    db.commit()
    return render(db, user)


@router.put("/settings")
def settings(body: DexSettings, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(Setting, (user.id, BY_SETS))
    if row is None:
        row = Setting(user_id=user.id, key=BY_SETS)
        db.add(row)
    row.value = "1" if body.by_sets else "0"
    db.commit()
    return render(db, user)
