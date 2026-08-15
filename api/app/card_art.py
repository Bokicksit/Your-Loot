"""Point card pictures at a host that offered to serve them.

Every card in the catalogue is seeded with an image URL on
`images.pokemontcg.io`, which belongs to the project that publishes the card
dump. Nobody there agreed to carry our traffic. On one household that is a
handful of requests and no one notices; served to everybody from one origin it
is somebody else's bandwidth bill, and the day they get tired of it every
picture in the app breaks at once.

TCGdex publishes its assets under MIT for exactly this use, so this walks the
catalogue and moves each card onto that host where the art exists.

It does not exist for all of them. About one card in twenty has no TCGdex art,
and the gaps are not spread evenly — Shiny Vault, the Trainer Galleries and
the Galarian Gallery have none at all, and those are the subsets people build
master binders out of. So this is a preference, not a migration: a card TCGdex
cannot picture keeps the URL it already had. Some hotlinking remains, and that
is the right trade against blanking the art on the best part of the app.

Two things are never touched: a photograph the collector took themselves, and
a card already moved by an earlier run.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.tcgdex import ASSETS as TCGDEX_ASSETS, tcgdex_client
from app.models import CardAttrs, CollectionItem, Module

# TCGDEX_ASSETS is their host, imported rather than spelled again: recognising
# it is how a second run knows there is nothing left to do for a card, and how
# the seed knows not to undo this.

# A photograph the collector uploaded lives on this server and outranks
# anything a catalogue has to offer — it is a picture of *their* card.
OWN_PHOTO = "/images/"


def settled(url: str | None) -> bool:
    """Is this card's picture already where it should be?"""
    u = url or ""
    return u.startswith(OWN_PHOTO) or u.startswith(TCGDEX_ASSETS)


def number_key(number: str | None) -> str:
    """"173" == "0173", while TG12 and 4a stay exactly themselves.

    The same rule the card search matches numbers by, because a card that
    resolves one way when you search for it and another way here would take
    its picture from a different card.
    """
    return (number or "").strip().lstrip("0").upper()


def art_by_number(client, set_id: str) -> dict[str, str]:
    """Every picture TCGdex has for one set, keyed by printed number.

    One request per set, not per card: the set listing carries the art URL,
    and asking per card would be twenty thousand requests to learn the same
    thing.
    """
    out: dict[str, str] = {}
    for card in client.cards_in_set(set_id):
        if card.get("image_url"):
            out[number_key(card.get("card_number"))] = card["image_url"]
    return out


def backfill(
    db: Session,
    client=None,
    only: str | None = None,
    write: bool = True,
    log=lambda _: None,
) -> dict:
    """Move what can be moved. Safe to run twice; the second run does nothing.

    `only` restricts it to a single set code, which is what makes this
    bearable to test and to retry after a set fails.

    `write=False` counts without changing anything. It has to be decided here
    rather than rolled back by the caller: this commits as it goes, so that a
    catalogue-wide run that dies on set one hundred keeps the ninety-nine.
    """
    client = client or tcgdex_client
    sets = client.all_sets()

    q = select(CardAttrs.set_code, CardAttrs.set_name).distinct()
    if only:
        q = q.where(CardAttrs.set_code == only)
    ours = [(c, n) for c, n in db.execute(q) if c]

    moved = kept = unmatched_sets = 0
    # by code, explicitly: set_name is nullable and sorting whole tuples
    # trips over comparing None to a string
    for set_code, set_name in sorted(ours, key=lambda r: r[0]):
        their_id = client.set_id_for(set_name or set_code, code=set_code, sets=sets)
        if not their_id:
            unmatched_sets += 1
            log(f"  {set_code:14} no match on TCGdex — left alone")
            continue

        try:
            art = art_by_number(client, their_id)
        except Exception as e:
            # one set the API stumbles on must not cost the whole catalogue
            log(f"  {set_code:14} lookup failed ({e}) — left alone")
            continue

        rows = db.execute(
            select(CollectionItem, CardAttrs)
            .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
            .where(
                CollectionItem.module == Module.cards.value,
                CardAttrs.set_code == set_code,
            )
        ).all()

        set_moved = set_kept = 0
        for item, attrs in rows:
            if settled(item.image_url):
                continue
            url = art.get(number_key(attrs.card_number))
            if url:
                item.image_url = url
                set_moved += 1
            else:
                set_kept += 1
        if write:
            db.commit()
        else:
            db.rollback()

        moved += set_moved
        kept += set_kept
        log(f"  {set_code:14} -> {their_id:14} moved {set_moved}, no art {set_kept}")

    return {
        "moved": moved,
        "kept": kept,
        "sets_unmatched": unmatched_sets,
        "sets": len(ours),
    }
