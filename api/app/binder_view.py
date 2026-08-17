"""Reading a binder — any of the three kinds — into one shape.

The kinds differ in where their slots come from and in what fills them, and
those two differences are the whole of it.

A **dex** binder has 1,025 slots and many cards can fill each one, so filling
one is a choice you make: you own six Charizards and the binder holds the one
you picked. A **set** binder has one slot per card in the set and exactly one
card fits each, so there is nothing to choose — owning the card fills the
slot. Asking somebody to file 180 Prismatic Evolutions cards by hand to see
which they are missing would be a worse chore than counting them in the
binder itself. A **custom** binder has no universe at all; its slots are what
you put in it, in the order you put them.

So `binder_slot` rows mean slightly different things per kind, which is the
price of one table: on a dex binder a row *is* the filing, on a set binder a
row is an override or a keeper flag laid over what ownership already says, and
on a custom binder the row is the slot.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.binders import CUSTOM, DEX, SET, page_count
from app.models import (
    BinderSlot,
    CardAttrs,
    CardPrinting,
    CollectionItem,
    Module,
    Owned,
    User,
)
from app.printings import rarity_mark

MAX_DEX = 1025


def species_names(db: Session, max_dex: int = 0) -> dict[int, str]:
    """A plain species name for every dex number the catalogue knows.

    The shortest title is a decent proxy for the species: "Charizard" beats
    "Charizard ex", which beats "M Charizard EX". That worked for as long as
    every card was English.

    It stopped the day the Japanese catalogue arrived. リザードン is five
    characters and Charizard is nine, so counting characters alone renamed a
    thousand Pokédex slots into Japanese — a shelf of English cards labelled
    in a language the owner may not read. So English is asked first and the
    rest only fills the gaps, which is what a Japanese-exclusive species
    would need and what nothing else should touch.

    Written once and read twice, because there are two Pokédex builders in
    this codebase and the last thing to exist in only one of them was a limit
    that then silently did nothing.
    """
    ceiling = max_dex or MAX_DEX

    def shortest(only=None) -> dict[int, str]:
        q = (
            select(CardAttrs.national_dex_no, CollectionItem.title)
            .join(CollectionItem, CollectionItem.id == CardAttrs.item_id)
            .where(CardAttrs.national_dex_no.is_not(None))
        )
        if only is not None:
            q = q.where(only)
        out: dict[int, str] = {}
        for dex, title in db.execute(q):
            if dex is None or dex > ceiling:
                continue
            if dex not in out or len(title) < len(out[dex]):
                out[dex] = title
        return out

    names = shortest(CardAttrs.language == "en")
    for dex, title in shortest().items():
        names.setdefault(dex, title)
    return names


def natural_key(number: str | None):
    """Sort card numbers the way they are printed.

    They are text, and they have to be: `TG12`, `101a`, `SV049`, and in one
    set a card numbered `!`. Plain lexical order puts 10 before 2 and buries
    the promos; this splits digits from the rest so 2 < 10 < 101a < TG12, with
    anything unnumbered last.
    """
    parts = [p for p in re.split(r"(\d+)", (number or "").strip()) if p]
    if not parts:
        return ((1, "￿"),)
    return tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts)


def _printings(rows, master: bool) -> list[str]:
    """The slots one card earns.

    A plain set binder gives every card one, whatever it was printed as. A
    master binder gives it one per printing — but only where we know them.
    Where nobody has asked TCGdex, or TCGdex does not carry the card, there
    are no rows and it falls back to a single slot: not knowing of a Poké Ball
    parallel is not the same as knowing there is not one.
    """
    if not master or not rows:
        return [""]
    return [r.code for r in rows]


# What a copy's own `variant` field can say, mapped onto printing codes. It
# has only ever offered three answers, so it can name a plain print, a
# parallel or a holo and nothing finer — a Poké Ball parallel is not something
# a copy can currently claim to be, which is why the fallback below matters.
COPY_VARIANT_CODE = {"non-holo": "n", "reverse holo": "r", "holo": "h"}


def _place_copies(mine, printings, slots, num) -> dict:
    """Decide which of your copies sits in which printing's slot.

    The obvious rule — a copy fills the slot matching the print style written
    on it — is wrong here, and quietly. Of 943 card copies on the install this
    was written against, 823 have no print style recorded at all, and a
    handful record one the card was never printed in. Under a strict match a
    master binder told its owner he had 24 of a set he had 34 of: every
    unrecorded copy fell through, and a card you own showed as a gap.

    A binder must never do that. So: anything pinned to a slot by hand wins,
    then copies that name their printing take it, then whatever is left fills
    the remaining slots in order. Every copy you own lands somewhere, and the
    count matches what is in your hands.
    """
    placed: dict[str, Owned] = {}
    left = list(mine)

    # a copy pinned to a slot by hand wins outright — it is the one decision
    # here that somebody actually made
    for v in printings:
        s = slots.get((num, v))
        if s and s.owned_id:
            pin = next((o for o in left if o.id == s.owned_id), None)
            if pin:
                placed[v] = pin
                left.remove(pin)

    # then the ones that say what they are
    for v in printings:
        if v in placed or not v:
            continue
        hit = next(
            (o for o in left
             if COPY_VARIANT_CODE.get((o.variant or "").strip().casefold()) == v),
            None,
        )
        if hit:
            placed[v] = hit
            left.remove(hit)

    # then everything else, in order, so nothing you own goes unshown
    for v in printings:
        if v in placed:
            continue
        if left:
            placed[v] = left.pop(0)
    return placed


def _card_out(item: CollectionItem, copy: Owned | None):
    if item is None:
        return None
    a = item.card_attrs
    return {
        "id": item.id,
        "owned_id": copy.id if copy else None,
        "title": item.title,
        "image_url": item.image_url,
        "set_name": a.set_name if a else None,
        "set_abbr": a.set_abbr if a else None,
        "set_total": a.set_total if a else None,
        "set_year": a.set_year if a else None,
        "card_number": a.card_number if a else None,
        "rarity": a.rarity if a else None,
        "layer": (a.layer or 1) if a else 1,
        "variant": copy.variant if copy else None,
        "stamp": copy.stamp if copy else None,
        "condition": copy.condition if copy else None,
        "grader": copy.grader if copy else None,
        "grade": copy.grade if copy else None,
    }


def _slots_of(db: Session, binder_id: int) -> dict[tuple[str | None, str], BinderSlot]:
    rows = db.scalars(
        select(BinderSlot)
        .where(BinderSlot.binder_id == binder_id)
        .options(joinedload(BinderSlot.item).joinedload(CollectionItem.card_attrs))
    ).unique().all()
    return {(s.slot_key, s.variant or ""): s for s in rows}


def _copy_map(db: Session, owned_ids: set[int]) -> dict[int, Owned]:
    if not owned_ids:
        return {}
    rows = db.scalars(select(Owned).where(Owned.id.in_(owned_ids))).all()
    return {o.id: o for o in rows}


def _dex_entries(db: Session, binder, user_id: int):
    """One slot per national dex number; the occupant is whatever was filed.

    How far it runs depends on the plan where the server charges for one —
    the first generation is a line people already know, and it is a shorter
    binder rather than a different feature.

    Anything filed above that line is hidden, never deleted. Somebody whose
    plan lapses still owns every card they filed; the slots come back the
    moment they subscribe again, because nothing moved.
    """
    from app.limits import dex_ceiling

    ceiling = dex_ceiling(db.get(User, user_id))
    slots = _slots_of(db, binder.id)
    filed = {s.owned_id for s in slots.values() if s.owned_id}
    copies = _copy_map(db, filed)

    items = {}
    if filed:
        rows = db.scalars(
            select(CollectionItem)
            .where(CollectionItem.id.in_({c.item_id for c in copies.values()}))
            .options(joinedload(CollectionItem.card_attrs))
        ).unique().all()
        items = {i.id: i for i in rows}

    names = species_names(db)

    for n in range(1, ceiling + 1):
        s = slots.get((str(n), ""))
        copy = copies.get(s.owned_id) if s and s.owned_id else None
        item = items.get(copy.item_id) if copy else None
        card = _card_out(item, copy)
        yield {
            "key": str(n),
            "label": f"#{n:03d}",
            "name": names.get(n),
            "card": card,
            "final": bool(s and s.happy),
            "state": "missing" if card is None else ("one" if s and s.happy else "upgrade"),
        }


def _set_entries(db: Session, binder, user_id: int):
    """One slot per card in the set — and owning the card fills it.

    A slot row is only consulted for the keeper flag or to pin one particular
    copy; without one, the slot is filled if you own the card at all.
    """
    cards = db.scalars(
        select(CollectionItem)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .where(
            CollectionItem.module == Module.cards.value,
            CardAttrs.set_code == binder.set_code,
        )
        .options(joinedload(CollectionItem.card_attrs), selectinload(CollectionItem.owned))
    ).unique().all()

    printings_by_item: dict[int, list] = {}
    if binder.master and cards:
        for row in db.scalars(
            select(CardPrinting)
            .where(CardPrinting.item_id.in_([c.id for c in cards]))
            .order_by(CardPrinting.item_id, CardPrinting.position)
        ).all():
            printings_by_item.setdefault(row.item_id, []).append(row)
    cards.sort(key=lambda i: natural_key(i.card_attrs.card_number if i.card_attrs else None))

    slots = _slots_of(db, binder.id)
    for item in cards:
        a = item.card_attrs
        num = (a.card_number if a else None) or ""
        mine = [o for o in item.owned if o.user_id == user_id]

        rows = printings_by_item.get(item.id)
        printings = _printings(rows, binder.master)
        by_code = {r.code: r for r in (rows or [])}
        placed = _place_copies(mine, printings, slots, num)

        for variant in printings:
            s = slots.get((num, variant))
            row = by_code.get(variant)
            copy = placed.get(variant)
            card = _card_out(item, copy) if copy else None
            yield {
                "key": num,
                # the standard print has no suffix, so it must not pick up the
                # space that would have separated one
                "label": " ".join(x for x in (num, (row.short if row else "")) if x),
                "variant": variant,
                "printing": row.label if row else None,
                "rarity_mark": rarity_mark(a.rarity if a else None),
                # A set slot names one exact card, and says so whether or not
                # you own it — which is what lets an empty slot be filled in
                # place instead of sending you off to search for something the
                # binder already knew.
                "item_id": item.id,
                "name": item.title,
                # the art shows whether or not you own it — a set binder is a
                # list of what exists, and the gap should look like the card
                # it wants
                "art": item.image_url,
                "card": card,
                # No keeper flag here. "The one" answers "which of my six
                # Charizards lives in this slot", and a set slot has no such
                # question — it names one exact card.
                "final": False,
                "state": "missing" if copy is None else "have",
            }


def _custom_entries(db: Session, binder, user_id: int):
    """Whatever you put in it, in the order you put it."""
    rows = db.scalars(
        select(BinderSlot)
        .where(BinderSlot.binder_id == binder.id)
        .options(joinedload(BinderSlot.item).joinedload(CollectionItem.card_attrs))
        .order_by(BinderSlot.position, BinderSlot.id)
    ).unique().all()
    copies = _copy_map(db, {s.owned_id for s in rows if s.owned_id})

    for n, s in enumerate(rows, start=1):
        copy = copies.get(s.owned_id) if s.owned_id else None
        item = s.item or (copy.item if copy else None)
        card = _card_out(item, copy) if item else None
        yield {
            "key": str(s.id),
            "label": str(n),
            "name": item.title if item else None,
            "art": item.image_url if item else None,
            "card": card,
            # nor here: a custom slot holds the card you put in it
            "final": False,
            "state": "missing" if copy is None else "have",
            # A page with nothing on it, rather than a card you have not got
            # yet. The set binders' gaps know what they are waiting for and
            # show it dimmed; this one is waiting for nothing, and should look
            # like the space it is.
            "blank": item is None,
        }


BUILDERS = {DEX: _dex_entries, SET: _set_entries, CUSTOM: _custom_entries}


def render(db: Session, binder, user_id: int) -> dict:
    entries = list(BUILDERS[binder.kind](db, binder, user_id))
    filled = sum(1 for e in entries if e["card"])
    return {
        "binder": {
            "id": binder.id,
            "name": binder.name,
            "kind": binder.kind,
            "set_code": binder.set_code,
            "master": binder.master,
            "image_url": binder.image_url,
            "color": binder.color,
            # the shape it is drawn in, and the page count that follows from
            # it — derived here rather than stored, so it cannot disagree with
            # the number of slots actually present
            "rows": binder.rows,
            "cols": binder.cols,
            "double_page": binder.double_page,
            "allow_ja": binder.allow_ja,
            "pages": page_count(binder, len(entries)),
            "total": len(entries),
            "filled": filled,
            "missing": len(entries) - filled,
            "final": sum(1 for e in entries if e["final"]),
        },
        "entries": entries,
    }
