"""Filing cards into binders.

The rules that used to live in `_enforce_single_binder` are mostly gone,
because the unique index on (binder, slot, variant) enforces them now. A slot
holds one card; putting a second one in swaps the first out, which is what
happens when you do it to a real binder.

What is left here is the vocabulary: get me this person's Pokédex, file this
copy in that slot, take it out, mark it as the one.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Binder, BinderSlot, Owned

DEX = "dex"
SET = "set"
CUSTOM = "custom"


def dex_binder(db: Session, user_id: int, create: bool = True) -> Binder | None:
    """The Pokédex, made on first use.

    Before binders were rows, everybody had one whether they used it or not.
    Now it appears the first time somebody files a card, which is why almost
    everything that touches it asks for it this way rather than assuming.
    """
    binder = db.scalar(
        select(Binder).where(Binder.user_id == user_id, Binder.kind == DEX)
    )
    if binder is None and create:
        binder = Binder(user_id=user_id, name="National Pokédex", kind=DEX)
        db.add(binder)
        db.flush()
    return binder


def slot(db: Session, binder: Binder, key: str, variant: str = "") -> BinderSlot | None:
    return db.scalar(
        select(BinderSlot).where(
            BinderSlot.binder_id == binder.id,
            BinderSlot.slot_key == key,
            BinderSlot.variant == (variant or ""),
        )
    )


def file_copy(
    db: Session, binder: Binder, key: str, owned_id: int,
    item_id: int | None = None, variant: str = "",
) -> BinderSlot:
    """Put a copy in a slot, displacing whatever was there.

    Displacing rather than refusing is deliberate: the binder is a physical
    thing and this is the physical action. The card that comes out is still
    owned, it is just back in the box.
    """
    # Assigned through the relationship rather than by id, so the copy's own
    # `binder_slots` collection is right immediately. The session does not
    # expire on commit, and `in_binder` is read off that collection to build
    # the response — set the id alone and the reply describes the binder as it
    # was a moment ago.
    copy = db.get(Owned, owned_id)
    existing = slot(db, binder, key, variant)
    if existing is None:
        existing = BinderSlot(
            binder_id=binder.id, slot_key=key, variant=variant or "", item_id=item_id
        )
        existing.owned = copy
        db.add(existing)
    else:
        existing.owned = copy
        if item_id is not None:
            existing.item_id = item_id
    db.flush()
    return existing


def unfile(db: Session, owned_id: int, binder_id: int | None = None) -> None:
    """Take a copy out — of one binder, or of every binder it is in.

    A slot that is only remembered because something was in it goes with it.
    A slot carrying the keeper flag stays, emptied: "I was happy with what was
    here" is worth keeping when you pull the card out to trade it, and an
    empty slot reads as missing either way.
    """
    q = select(BinderSlot).where(BinderSlot.owned_id == owned_id)
    if binder_id is not None:
        q = q.where(BinderSlot.binder_id == binder_id)
    for s in db.scalars(q).all():
        s.owned = None  # detaches from the copy's collection, both ways
        if not s.happy:
            db.delete(s)
    db.flush()


def set_happy(db: Session, binder: Binder, key: str, happy: bool) -> BinderSlot:
    """'I am happy with this one' — it stays even though better exists."""
    s = slot(db, binder, key)
    if s is None:
        s = BinderSlot(binder_id=binder.id, slot_key=key, happy=happy)
        db.add(s)
    else:
        s.happy = happy
    db.flush()
    return s


def filed_anywhere():
    """A correlated EXISTS for "this copy is in some binder".

    The card list uses it to hide cards that are already in a binder, which is
    the setting's whole purpose — the list is meant to be what is *not* on
    display. Any binder counts, not just the Pokédex: a card in the
    Celebrations binder is no less on display for it.
    """
    return select(BinderSlot.id).where(BinderSlot.owned_id == Owned.id).exists()


def purge_owned(db: Session, owned_id: int) -> None:
    """The copy is gone, so it is in no binders. Slots that only existed to
    hold it go; keeper flags stay behind on an empty slot."""
    unfile(db, owned_id)


def clear_binder(db: Session, binder_id: int) -> None:
    db.execute(delete(BinderSlot).where(BinderSlot.binder_id == binder_id))


# --- master sets -----------------------------------------------------------


def printings_known(db: Session, set_code: str) -> bool:
    """Has anybody asked TCGdex about this set yet?"""
    from app.models import CardAttrs, CardPrinting, CollectionItem

    without = db.scalar(
        select(func.count()).select_from(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            CardAttrs.set_code == set_code,
            ~select(CardPrinting.id)
            .where(CardPrinting.item_id == CollectionItem.id).exists(),
        )
    )
    return not without


def learn_printings(db: Session, set_code: str, set_name: str | None) -> dict:
    """Fetch and keep every way each card in a set was printed.

    Once per set, the first time somebody makes a master binder of it. A card
    TCGdex does not carry keeps no rows and gets a single unnamed slot, which
    is the honest fallback: we do not know of another printing, so we do not
    invent one.
    """
    from app.integrations.tcgdex import tcgdex_client
    from app.models import CardAttrs, CardPrinting, CollectionItem
    from app.printings import code_for, label_for, short_for

    tcg_id = tcgdex_client.set_id_for(set_name or "", set_code)
    if not tcg_id:
        return {"matched": False, "set": set_code, "learned": 0, "printings": 0}

    found = tcgdex_client.printings_in_set(tcg_id)
    by_number = {k.lstrip("0") or k: v for k, v in found.items()}

    rows = db.execute(
        select(CollectionItem.id, CardAttrs.card_number)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(CardAttrs.set_code == set_code)
    ).all()

    learned = written = 0
    for item_id, number in rows:
        key = (number or "").lstrip("0") or (number or "")
        variants = by_number.get(key) or by_number.get(number or "")
        if not variants:
            continue
        db.execute(delete(CardPrinting).where(CardPrinting.item_id == item_id))
        seen = set()
        for n, v in enumerate(variants):
            kind, foil = v.get("type"), v.get("foil")
            stamps, size = v.get("stamp"), v.get("size")
            code = code_for(kind, foil, stamps, size)
            # the same combination twice on one card is a duplicate, not a
            # second box on the checklist
            if code in seen:
                continue
            seen.add(code)
            db.add(CardPrinting(
                item_id=item_id, code=code, kind=(kind or "holo"), foil=foil,
                stamp=",".join(stamps or []) or None, size=size,
                label=label_for(kind, foil, stamps, size),
                short=short_for(kind, foil, stamps, size),
                position=n,
            ))
            written += 1
        learned += 1
    db.commit()
    return {
        "matched": True, "set": set_code, "tcgdex_id": tcg_id,
        "learned": learned, "unmatched": len(rows) - learned, "printings": written,
    }
