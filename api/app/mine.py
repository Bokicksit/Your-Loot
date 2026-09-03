"""One person's collection, out and back in.

The whole-server backup next door is the operator's copy of the machine.
This is yours: the part of the database that is about you, in a file you can
carry to another install and load into your own account there.

Three rules hold it together.

**It can only ever touch the person asking.** Every row it writes names the
caller as its owner, and every row it clears is one it found under their id.
There is no argument that widens it, no admin flag that makes it whole-server
— the file format cannot express somebody else's collection, so no request
can ask for one.

**The catalogue is matched, not carried.** A Charizard on your server and a
Charizard on ours are different rows with different ids, and copying the id
would file your cards against whatever happened to hold that number here. So
each item travels as its identity — where it came from and its id there —
and the import finds the local row or creates it.

**What nobody agreed on stays yours.** An item you typed in by hand has no
such identity, so an import has nothing to match and has to create a row for
it. Those rows are marked as belonging to you, which keeps "Dad's old NES,
boxed" out of everybody else's search results — see tenancy.visible().

What is deliberately not in the file: your password, your plan, your screen
name, whether you are an admin, and — the one worth saying out loud — which
shelves you publish. Publishing is a decision about the server the profile
lives on, and a restore must never be the thing that turns it on.
"""

import io
import json
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Date, DateTime, delete, select
from sqlalchemy.orm import Session

from app.config import settings as cfg
from app.models import (
    AmiiboAttrs,
    Binder,
    BinderSlot,
    BookAttrs,
    CardAttrs,
    CollectionItem,
    ComicAttrs,
    GameAttrs,
    ItemTag,
    LegoAttrs,
    MovieAttrs,
    Owned,
    RecordAttrs,
    Setting,
    Tag,
    Wanted,
)
from app.modules import available
from app.version import VERSION

FORMAT = "yourloot-collection"
SCHEMA = 1
MAX_UPLOAD = 200 * 1024 * 1024

# The phrase somebody has to type. A restore replaces what is in the account
# with what is in the file, which is what "restore" means and is still worth
# making somebody spell out.
CONFIRM = "RESTORE"

ATTRS = {
    "cards": CardAttrs,
    "amiibo": AmiiboAttrs,
    "games": GameAttrs,
    "movies": MovieAttrs,
    "books": BookAttrs,
    "records": RecordAttrs,
    "lego": LegoAttrs,
    "comics": ComicAttrs,
}

# Settings that describe this server rather than this person. A profile is
# published on the install it lives on; carrying the choice to another one
# would publish a collection somewhere its owner never asked for.
#
# The sync settings are local for the opposite reason: they describe where
# *this* install sends its collection. Carried along, a mirror would inherit
# the instruction to mirror itself somewhere, token included.
SYNC_KEYS = {
    "sync_url", "sync_token", "sync_nightly",
    "sync_last_at", "sync_last_result", "sync_last_error",
}
# And what the receiving end knows about itself: that it is a mirror, of
# what, since when. A fact about this account on this server.
MIRROR_KEYS = {"mirrored_at", "mirror_source"}
LOCAL_ONLY = {"public_collections", "public_loose"} | SYNC_KEYS | MIRROR_KEYS


def _plain(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def _row(obj, drop=("id",)):
    """A model row as plain data, without the keys that only mean something
    in the database it came from."""
    return {
        c.name: _plain(getattr(obj, c.name))
        for c in obj.__table__.columns
        if c.name not in drop
    }


# ------------------------------------------------------------------- out


def _identity(item: CollectionItem, mine: bool) -> dict:
    """An item as something another install can recognise.

    `ref` is the id it had here, and it is used for nothing except joining
    the rest of this file together — the import throws it away once it has
    found or made the local row.
    """
    row = _attrs_of(item)
    attrs = _row(row, drop=("id", "item_id")) if row is not None else None
    return {
        "ref": item.id,
        "module": item.module,
        "source": item.source,
        "external_id": item.external_id,
        "title": item.title,
        "image_url": item.image_url,
        "notes": item.notes,
        # a row this person made rather than one everybody shares
        "mine": mine,
        "attrs": attrs,
    }


def _attrs_of(item: CollectionItem):
    # Every module ATTRS knows how to rebuild has to be readable here too.
    # amiibo was missing, so figures exported with attrs: null and came back
    # from a restore with no character, series or type — the import side had
    # been ready for them the whole time.
    for name in ("card_attrs", "amiibo_attrs", "game_attrs", "movie_attrs",
                 "book_attrs", "record_attrs", "lego_attrs", "comic_attrs"):
        row = getattr(item, name, None)
        if row is not None:
            return row
    return None


def gather(db: Session, user) -> dict:
    """Everything of this person's, and the identity of what it points at."""
    owned = db.scalars(select(Owned).where(Owned.user_id == user.id)).all()
    wanted = db.scalars(select(Wanted).where(Wanted.user_id == user.id)).all()
    tags = db.scalars(select(Tag).where(Tag.user_id == user.id)).all()
    binders = db.scalars(select(Binder).where(Binder.user_id == user.id)).all()
    binder_ids = [b.id for b in binders]
    slots = (
        db.scalars(
            select(BinderSlot).where(BinderSlot.binder_id.in_(binder_ids))
        ).all()
        if binder_ids
        else []
    )
    tag_links = (
        db.scalars(
            select(ItemTag).where(ItemTag.tag_id.in_([t.id for t in tags]))
        ).all()
        if tags
        else []
    )
    prefs = db.scalars(select(Setting).where(Setting.user_id == user.id)).all()

    # every catalogue row anything of theirs points at
    refs = {o.item_id for o in owned} | {w.item_id for w in wanted}
    refs |= {l.item_id for l in tag_links}
    refs |= {s.item_id for s in slots if s.item_id}
    items = (
        db.scalars(select(CollectionItem).where(CollectionItem.id.in_(refs))).all()
        if refs
        else []
    )

    return {
        "format": FORMAT,
        "schema": SCHEMA,
        "app_version": VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "modules": available(),
        "items": [_identity(i, i.private_to == user.id) for i in items],
        "owned": [_row(o, drop=("id", "user_id")) | {"ref": o.item_id} for o in owned],
        "wanted": [_row(w, drop=("id", "user_id")) | {"ref": w.item_id} for w in wanted],
        "tags": [
            _row(t, drop=("id", "user_id"))
            | {"items": [l.item_id for l in tag_links if l.tag_id == t.id]}
            for t in tags
        ],
        "binders": [
            _row(b, drop=("id", "user_id"))
            | {
                "slots": [
                    _row(s, drop=("id", "binder_id"))
                    # a slot points at a copy, and copies are matched by where
                    # they sit rather than by an id that will not survive
                    | {"owned_at": _copy_index(owned, s.owned_id)}
                    for s in slots
                    if s.binder_id == b.id
                ]
            }
            for b in binders
        ],
        "settings": [
            {"key": p.key, "value": p.value}
            for p in prefs
            if p.key not in LOCAL_ONLY
        ],
    }


def _copy_index(owned, owned_id):
    """Which copy in this file a slot is holding, by position.

    Copies have no identity of their own — two NM copies of the same card are
    genuinely the same thing — so the file refers to them by where they are
    in its own list, and the import rebuilds the same list in the same order.
    """
    if owned_id is None:
        return None
    for n, o in enumerate(owned):
        if o.id == owned_id:
            return n
    return None


def _images_for(payload: dict) -> set[str]:
    """The uploaded files this collection actually points at."""
    names = set()
    for item in payload["items"]:
        url = item.get("image_url") or ""
        if url.startswith("/images/"):
            names.add(url.rsplit("/", 1)[-1])
    for binder in payload["binders"]:
        url = binder.get("image_url") or ""
        if url.startswith("/images/"):
            names.add(url.rsplit("/", 1)[-1])
    return names


def to_zip(db: Session, user, payload: dict | None = None,
           only_images: set[str] | None = None) -> bytes:
    """The collection as a file.

    `only_images` narrows which photographs ride along — for a push to a
    server that has already said which ones it holds. None means all of them,
    which is what a backup wants: a file that stands on its own.
    """
    payload = payload if payload is not None else gather(db, user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("collection.json", json.dumps(payload, indent=1))
        root = Path(cfg.image_dir)
        wanted = _images_for(payload)
        if only_images is not None:
            wanted &= set(only_images)
        for name in wanted:
            path = root / name
            if path.is_file():
                z.write(path, f"images/{name}")
    return buf.getvalue()


def images_missing(names) -> list[str]:
    """Of these uploaded-file names, the ones this install does not hold.

    Bare names only — a name that could climb out of the directory is not a
    file this server has, whatever the disk says.
    """
    root = Path(cfg.image_dir)
    out = []
    for raw in names:
        name = str(raw or "")
        if not name or "/" in name or "\\" in name or name.startswith("."):
            continue
        if not (root / name).is_file():
            out.append(name)
    return out


# -------------------------------------------------------------------- in


class Refused(Exception):
    """A file this install will not load, with the reason a person needs."""


NOT_OURS = "That does not look like a Your Loot collection file."
WRONG_ONE = (
    "That is a backup of a whole server, not of one collection. The file for "
    "this is the one from Back up my collection."
)


def _open(raw: bytes) -> tuple[dict, zipfile.ZipFile]:
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise Refused(NOT_OURS) from None

    names = set(z.namelist())
    if "collection.json" not in names:
        # The two files look alike from the outside and are not. Loading the
        # wrong one is the mistake worth naming rather than shrugging at.
        raise Refused(WRONG_ONE if "database.json" in names else NOT_OURS)

    try:
        payload = json.loads(z.read("collection.json"))
    except json.JSONDecodeError:
        raise Refused(NOT_OURS) from None
    if payload.get("format") != FORMAT:
        raise Refused(WRONG_ONE if payload.get("format") == "yourloot-backup" else NOT_OURS)
    if int(payload.get("schema", 0)) > SCHEMA:
        raise Refused(
            "That file was made by a newer version of Your Loot than this "
            "server is running. Update first, then restore."
        )
    return payload, z


def _clear(db: Session, user_id: int) -> None:
    """Everything of theirs, and nothing of anybody else's.

    Every statement here is bounded by the user id — the two that are not
    reach their rows through one that is, which is why they are written as
    subqueries rather than joins.
    """
    # Binders are not cleared here. They are matched by uid and updated in
    # place by load(), so that a binder keeps its id — and the public link
    # somebody was given to it — across a restore or a nightly mirror. Their
    # slots are replaced there too, per binder.
    tags = select(Tag.id).where(Tag.user_id == user_id)
    db.execute(delete(ItemTag).where(ItemTag.tag_id.in_(tags)))
    db.execute(delete(Tag).where(Tag.user_id == user_id))
    db.execute(delete(Owned).where(Owned.user_id == user_id))
    db.execute(delete(Wanted).where(Wanted.user_id == user_id))
    # Catalogue rows that exist only because this person imported them once
    # before. Left behind they would pile up, one dead copy of every
    # hand-typed item per restore.
    db.execute(delete(CollectionItem).where(CollectionItem.private_to == user_id))


def _find_or_make(db: Session, spec: dict, user_id: int, here: set[str]):
    """The local row for an item in the file.

    Matched on where it came from, which is the one thing that means the same
    on both servers. Where there is no such identity — anything hand-typed —
    a row is created and marked as this person's, because nobody else agreed
    that it exists.
    """
    module = spec.get("module")
    if module not in ATTRS or module not in here:
        return None  # a collection this install does not carry

    source, external = spec.get("source"), spec.get("external_id")
    if source and external and not spec.get("mine"):
        found = db.scalar(
            select(CollectionItem).where(
                CollectionItem.source == source,
                CollectionItem.external_id == external,
            )
        )
        if found is not None:
            return found

    # Hand-typed, which is not "no source" — an item added by hand is stamped
    # 'manual' and carries no id at all. The absence of the id is the thing
    # that matters, so that is what is asked about.
    # Matched anyway, against rows that are also hand-typed and are either
    # this person's own or already shared here, because the alternative is a
    # second row every time somebody restores — a collection reloaded twice
    # would leave two of everything it could not identify. Restoring onto the
    # install a backup came from is the ordinary case and it should be a
    # no-op, not a slow leak.
    title = (spec.get("title") or "").strip()
    if title:
        found = db.scalar(
            select(CollectionItem)
            .where(
                CollectionItem.module == module,
                CollectionItem.external_id.is_(None),
                CollectionItem.title == title,
                (CollectionItem.private_to.is_(None))
                | (CollectionItem.private_to == user_id),
            )
            # a row of this person's own before one everybody shares
            .order_by(CollectionItem.private_to.is_(None), CollectionItem.id)
        )
        if found is not None:
            return found

    item = CollectionItem(
        module=module,
        title=(spec.get("title") or "Untitled")[:300],
        image_url=spec.get("image_url"),
        notes=spec.get("notes"),
        source=source if not spec.get("mine") else None,
        external_id=external if not spec.get("mine") else None,
        private_to=user_id if (spec.get("mine") or not (source and external)) else None,
    )
    db.add(item)
    db.flush()

    attrs = spec.get("attrs")
    if attrs:
        model = ATTRS[module]
        columns = {c.name for c in model.__table__.columns}
        db.add(model(item_id=item.id, **{
            k: v for k, v in attrs.items() if k in columns and k != "item_id"
        }))
        db.flush()
    return item


def _write_images(z: zipfile.ZipFile) -> int:
    """Photographs the person took, back on disk.

    Written under the name they had, which is what the rows point at. A file
    already there is left alone rather than overwritten: names are content
    hashes, so the one on disk is the same picture.
    """
    root = Path(cfg.image_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = 0
    for entry in z.namelist():
        if not entry.startswith("images/") or entry.endswith("/"):
            continue
        name = Path(entry).name
        if not name or "/" in name or "\\" in name or name.startswith("."):
            continue
        target = root / name
        if target.exists():
            continue
        target.write_bytes(z.read(entry))
        written += 1
    return written


def load(db: Session, user, raw: bytes, confirm: str) -> dict:
    """Replace this account's collection with the one in the file.

    Everything is worked out before anything is deleted, and the whole thing
    is one transaction — a file that turns out to be unreadable half way
    through leaves the account exactly as it was.
    """
    if (confirm or "").strip().upper() != CONFIRM:
        raise Refused(f'Type {CONFIRM} to confirm — this replaces what is in your account.')
    if len(raw) > MAX_UPLOAD:
        raise Refused("That file is too large to upload.")
    if not raw:
        raise Refused("That file is empty.")

    payload, z = _open(raw)
    here = set(available())
    check_plan(payload, user, here)

    _clear(db, user.id)

    # items first: everything else points at them
    items = {}
    skipped = 0
    for spec in payload.get("items", []):
        row = _find_or_make(db, spec, user.id, here)
        if row is None:
            skipped += 1
            continue
        items[spec.get("ref")] = row

    copies = []
    for spec in payload.get("owned", []):
        item = items.get(spec.get("ref"))
        if item is None:
            copies.append(None)   # keeps the positions the slots refer to
            continue
        row = Owned(**_fields(Owned, spec), user_id=user.id, item_id=item.id)
        db.add(row)
        copies.append(row)
    db.flush()

    for spec in payload.get("wanted", []):
        item = items.get(spec.get("ref"))
        if item is not None:
            db.add(Wanted(**_fields(Wanted, spec), user_id=user.id, item_id=item.id))

    for spec in payload.get("tags", []):
        tag = Tag(**_fields(Tag, spec), user_id=user.id)
        db.add(tag)
        db.flush()
        for ref in spec.get("items", []):
            item = items.get(ref)
            if item is not None:
                db.add(ItemTag(tag_id=tag.id, item_id=item.id))

    # Binders: found again rather than made again, so their ids hold. A file
    # from before uids is matched on what it can be — kind and set, or kind
    # and name — which is exact for set and dex binders and as good as a
    # custom binder's name is.
    existing = list(db.scalars(select(Binder).where(Binder.user_id == user.id)).all())
    by_uid = {b.uid: b for b in existing}
    claimed: set[int] = set()   # one local binder answers for one in the file
    kept: set[int] = set()
    for spec in payload.get("binders", []):
        fields = _fields(Binder, spec)
        want = fields.pop("uid", None)
        binder = by_uid.get(want) if want else None
        if binder is not None and binder.id in claimed:
            binder = None
        if binder is None:
            # not by that name — but this account may hold the same binder
            # under one of its own, which is the ordinary case for a Pokédex
            binder = _same_binder(spec, [b for b in existing if b.id not in claimed])
        if binder is None:
            binder = Binder(**fields, uid=want or str(uuid.uuid4()), user_id=user.id)
            db.add(binder)
            db.flush()
            existing.append(binder)
            by_uid[binder.uid] = binder
        else:
            for k, v in fields.items():
                setattr(binder, k, v)
            # take the sender's name for it, so the next send matches on the
            # uid directly — unless something else here already answers to it
            if want and want != binder.uid and want not in by_uid:
                by_uid.pop(binder.uid, None)
                binder.uid = want
                by_uid[want] = binder
            db.execute(delete(BinderSlot).where(BinderSlot.binder_id == binder.id))
            db.flush()
        claimed.add(binder.id)
        kept.add(binder.id)
        for slot in spec.get("slots", []):
            at = slot.get("owned_at")
            copy = copies[at] if isinstance(at, int) and 0 <= at < len(copies) else None
            item = items.get(slot.get("item_id"))
            db.add(BinderSlot(
                **_fields(BinderSlot, slot),
                binder_id=binder.id,
                owned_id=copy.id if copy is not None else None,
                item_id=item.id if item is not None else None,
            ))

    # a binder the file no longer has is one that was deleted at the source.
    # `existing` also holds the ones made just now, and their ids are in
    # `kept`, so they are not swept away by the pass that follows them.
    for b in existing:
        if b.id not in kept:
            db.execute(delete(BinderSlot).where(BinderSlot.binder_id == b.id))
            db.delete(b)
    db.flush()

    for pref in payload.get("settings", []):
        key = pref.get("key")
        if not key or key in LOCAL_ONLY:
            continue
        row = db.get(Setting, (user.id, key))
        if row is None:
            row = Setting(user_id=user.id, key=key)
            db.add(row)
        row.value = pref.get("value")

    images = _write_images(z)
    db.commit()

    return {
        "items": len(items),
        "copies": sum(1 for c in copies if c is not None),
        "wanted": len(payload.get("wanted", [])),
        "binders": len(payload.get("binders", [])),
        "tags": len(payload.get("tags", [])),
        "images": images,
        # said rather than swallowed: a collection this install does not
        # carry cannot be loaded, and somebody whose films vanished deserves
        # to be told why rather than left to notice
        "skipped": skipped,
        "from_version": payload.get("app_version"),
        "created_at": payload.get("created_at"),
    }


def _same_binder(spec: dict, candidates):
    """The binder here that the one in the file *is*, ignoring its name.

    Two jobs, and the second is the one that matters. A file written before
    uids existed carries none, so there is nothing to match on but identity.
    And an account that has used binders already made its own — a Pokédex
    appears the first time anybody files a card — so the incoming Pokédex
    carries a uid this account has never seen, matches nothing, and would be
    created a second time. There can only be one Pokédex per account and the
    database says so, so that attempt failed the whole load.

    Set and dex binders are identified by what they are *of*; a custom binder
    by its name, which is what a person would match them on too.
    """
    kind = spec.get("kind")
    for b in candidates:
        if b.kind != kind:
            continue
        if kind == "dex":
            return b   # there is only ever one
        if kind == "set":
            if (b.set_code or "") == (spec.get("set_code") or "") and bool(b.master) == bool(spec.get("master")):
                return b
        elif (b.name or "") == (spec.get("name") or ""):
            return b
    return None


def check_plan(payload: dict, user, here: set[str]) -> None:
    """Refuse a collection this account's plan could not hold.

    A restore was always somebody's own file back into their own account, so
    nothing here ever counted. A collection arriving from another server is
    a different thing: a free account on a hosted install can be sent two
    thousand cards from a home one, and loading them would put the account
    past a cap it could never have reached by hand. Better refused, and
    said, than loaded and quietly over.

    Counted the way the caps are: copies of cards, and binders besides the
    Pokédex. Cards from a collection this install does not carry are not
    counted, because they are not loaded either.
    """
    from app import limits

    if not limits.limited(user):
        return
    module_of = {i.get("ref"): i.get("module") for i in payload.get("items", [])}
    cards = sum(
        1 for o in payload.get("owned", [])
        if module_of.get(o.get("ref")) == "cards" and "cards" in here
    )
    cap = limits.card_limit()
    if cap and cards > cap:
        raise Refused(
            f"This collection has {cards} cards and the plan on this account "
            f"allows {cap}. Nothing was changed."
        )
    extra = sum(1 for b in payload.get("binders", []) if b.get("kind") != "dex")
    bcap = limits.binder_limit()
    if bcap and extra > bcap:
        raise Refused(
            f"This collection has {extra} binders besides the Pokédex and the "
            f"plan on this account allows {bcap}. Nothing was changed."
        )


def _fields(model, spec: dict) -> dict:
    """The columns of `model` that this row actually carries.

    Anything the file has and the model does not is dropped rather than
    refused: an older install reading a newer file should lose a field it
    never had, not the collection.
    """
    keep = {c.name for c in model.__table__.columns}
    skip = {"id", "user_id", "item_id", "binder_id", "owned_id", "tag_id", "ref"}
    out = {}
    for key, value in spec.items():
        if key not in keep or key in skip:
            continue
        column = model.__table__.columns[key]
        if isinstance(value, str) and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value)
        elif isinstance(value, str) and isinstance(column.type, Date):
            value = date.fromisoformat(value)
        out[key] = value
    return out
