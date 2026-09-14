"""Check set: which gaps in the Pokédex a set could close.

The Pokédex's Missing view can ask a set which of the empty slots it has a
card for. The answer is per dex number, with the card numbers to look for —
and Trainers, which have no dex number, are never part of it.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid

import pytest


@pytest.fixture
def a_set_with_pokemon(owner):
    """A small set: two cards of one Pokémon, one of another, and a Trainer."""
    from sqlalchemy import delete, select

    from app.db import SessionLocal
    from app.models import CardAttrs, CollectionItem, Module

    mark = uuid.uuid4().hex[:6]
    code = f"dex{mark}"
    cards = [
        ("Pikachu", "025", 25),
        ("Pikachu", "173", 25),      # a second printing of the same Pokémon
        ("Mewtwo", "150", 150),
        ("Professor's Research", "189", None),   # a Trainer fills no slot
    ]
    db = SessionLocal()
    try:
        for title, num, dex in cards:
            item = CollectionItem(
                module=Module.cards.value, title=f"{title} {code}", source="manual"
            )
            item.card_attrs = CardAttrs(
                set_code=code, set_name=f"Check Set {mark}", set_abbr="CHK",
                card_number=num, national_dex_no=dex, language="en",
            )
            db.add(item)
        db.commit()
        yield code
    finally:
        ids = [
            i for (i,) in db.execute(
                select(CollectionItem.id)
                .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
                .where(CardAttrs.set_code == code)
            ).all()
        ]
        if ids:
            db.execute(delete(CollectionItem).where(CollectionItem.id.in_(ids)))
            db.commit()
        db.close()


def test_a_set_says_which_pokemon_it_has_cards_for(owner, a_set_with_pokemon):
    r = owner.get(f"/api/cards/sets/{a_set_with_pokemon}/dex")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["set"]["code"] == a_set_with_pokemon
    assert body["set"]["abbr"] == "CHK"
    # one key per Pokémon, the card numbers in printed order, and no Trainer
    assert body["fills"] == {"25": ["025", "173"], "150": ["150"]}


def test_a_set_nobody_has_heard_of_is_a_404(owner):
    r = owner.get("/api/cards/sets/no-such-set/dex")
    assert r.status_code == 404
