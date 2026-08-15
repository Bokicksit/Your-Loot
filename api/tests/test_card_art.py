"""Whose CDN is serving the card pictures?

Every card is seeded pointing at images.pokemontcg.io. That is fine for one
household and rude at scale, so a shared install moves them onto TCGdex's
asset host — but only where the art exists, because a fifth of the chase
cards have none and a blank Shiny Vault is worse than a hotlinked one.

TCGdex is stubbed rather than called: what is worth protecting is which cards
get moved and which are left alone, and that is decided here, not there.

    docker compose -f compose.test.yaml run --rm tests
"""

import json
import uuid
from pathlib import Path

import pytest

from app.card_art import backfill, number_key, settled
from app.db import SessionLocal
from app.models import CardAttrs, CollectionItem, Module

POKEMONTCG = "https://images.pokemontcg.io/{}/{}.png"
TCGDEX = "https://assets.tcgdex.net/en/sv/zztest/{}/high.png"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def set_code():
    """A set nobody else's test will touch."""
    return f"zz{uuid.uuid4().hex[:8]}"


class FakeTCGdex:
    """Art for cards 1 and 3 of one set. Card 2 has none, as one in twenty
    genuinely does not."""

    def __init__(self, their_id="zztest", has_art=("1", "3")):
        self.their_id = their_id
        self.has_art = has_art
        self.set_requests = []

    def all_sets(self):
        return [{"id": self.their_id, "name": "ZZ Test Set"}]

    def set_id_for(self, name, code=None, sets=None):
        return self.their_id

    def cards_in_set(self, set_id):
        self.set_requests.append(set_id)
        return [
            {
                "card_number": n,
                "image_url": TCGDEX.format(n) if n in self.has_art else None,
            }
            for n in ("1", "2", "3")
        ]


def make_cards(db, set_code, numbers_and_urls):
    for number, url in numbers_and_urls:
        db.add(
            CollectionItem(
                module=Module.cards.value,
                source="ptcg",
                external_id=f"{set_code}-{number}",
                title=f"Test Card {number}",
                image_url=url,
                card_attrs=CardAttrs(set_code=set_code, set_name="ZZ Test Set",
                                     card_number=number),
            )
        )
    db.commit()


def cleanup(db, set_code):
    ids = [
        i for (i,) in db.query(CollectionItem.id)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .filter(CardAttrs.set_code == set_code)
    ]
    if ids:
        db.query(CardAttrs).filter(CardAttrs.item_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(CollectionItem).filter(CollectionItem.id.in_(ids)).delete(
            synchronize_session=False
        )
        db.commit()


def urls(db, set_code):
    return {
        a.card_number: i.image_url
        for i, a in db.query(CollectionItem, CardAttrs)
        .join(CardAttrs, CardAttrs.item_id == CollectionItem.id)
        .filter(CardAttrs.set_code == set_code)
    }


def test_art_moves_to_tcgdex_only_where_it_exists(db, set_code):
    """Card 2 has no TCGdex art. Leaving it on the old CDN is the point —
    the alternative is a hole in the binder."""
    make_cards(db, set_code, [
        ("1", POKEMONTCG.format(set_code, 1)),
        ("2", POKEMONTCG.format(set_code, 2)),
        ("3", POKEMONTCG.format(set_code, 3)),
    ])
    try:
        result = backfill(db, client=FakeTCGdex(), only=set_code)
        got = urls(db, set_code)

        assert result["moved"] == 2
        assert result["kept"] == 1
        assert got["1"] == TCGDEX.format("1")
        assert got["3"] == TCGDEX.format("3")
        assert got["2"] == POKEMONTCG.format(set_code, 2), "card 2 lost its picture"
    finally:
        cleanup(db, set_code)


def test_a_photograph_the_collector_took_is_never_touched(db, set_code):
    """Their own card, photographed by them, outranks any catalogue."""
    mine = "/images/my-charizard.jpg"
    make_cards(db, set_code, [("1", mine), ("3", POKEMONTCG.format(set_code, 3))])
    try:
        backfill(db, client=FakeTCGdex(), only=set_code)
        got = urls(db, set_code)

        assert got["1"] == mine, "a collector's own photo was overwritten"
        assert got["3"] == TCGDEX.format("3")
    finally:
        cleanup(db, set_code)


def test_running_it_twice_moves_nothing_the_second_time(db, set_code):
    make_cards(db, set_code, [("1", POKEMONTCG.format(set_code, 1))])
    try:
        first = backfill(db, client=FakeTCGdex(), only=set_code)
        second = backfill(db, client=FakeTCGdex(), only=set_code)

        assert first["moved"] == 1
        assert second["moved"] == 0, "a settled card was moved again"
        assert second["kept"] == 0, "a settled card was counted as missing art"
    finally:
        cleanup(db, set_code)


def test_a_dry_run_writes_nothing(db, set_code):
    """Reporting what would happen must not be how it happens."""
    make_cards(db, set_code, [("1", POKEMONTCG.format(set_code, 1))])
    try:
        result = backfill(db, client=FakeTCGdex(), only=set_code, write=False)
        db.expire_all()

        assert result["moved"] == 1, "a dry run should still count"
        assert urls(db, set_code)["1"] == POKEMONTCG.format(set_code, 1), \
            "a dry run wrote to the database"
    finally:
        cleanup(db, set_code)


def test_a_set_tcgdex_does_not_have_is_left_alone(db, set_code):
    """One set with no counterpart must not cost the other hundred and
    seventy — and must not blank the cards it does have."""
    class Unmatched(FakeTCGdex):
        def set_id_for(self, name, code=None, sets=None):
            return None

    make_cards(db, set_code, [("1", POKEMONTCG.format(set_code, 1))])
    try:
        result = backfill(db, client=Unmatched(), only=set_code)

        assert result["sets_unmatched"] == 1
        assert result["moved"] == 0
        assert urls(db, set_code)["1"] == POKEMONTCG.format(set_code, 1)
    finally:
        cleanup(db, set_code)


def test_a_set_that_fails_to_load_does_not_blank_its_cards(db, set_code):
    class Angry(FakeTCGdex):
        def cards_in_set(self, set_id):
            raise RuntimeError("TCGdex is having a morning")

    make_cards(db, set_code, [("1", POKEMONTCG.format(set_code, 1))])
    try:
        result = backfill(db, client=Angry(), only=set_code)

        assert result["moved"] == 0
        assert urls(db, set_code)["1"] == POKEMONTCG.format(set_code, 1)
    finally:
        cleanup(db, set_code)


def test_padded_numbers_match(db, set_code):
    """The dump writes 001 where TCGdex writes 1. Matching them literally
    would take a card's picture from whichever card happened to line up."""
    make_cards(db, set_code, [("001", POKEMONTCG.format(set_code, 1))])
    try:
        backfill(db, client=FakeTCGdex(), only=set_code)
        assert urls(db, set_code)["001"] == TCGDEX.format("1")
    finally:
        cleanup(db, set_code)


@pytest.mark.parametrize("number,expected", [
    ("001", "1"), ("1", "1"), ("TG12", "TG12"), ("tg12", "TG12"),
    ("4a", "4A"), (" 12 ", "12"), (None, ""),
])
def test_number_key(number, expected):
    assert number_key(number) == expected


@pytest.mark.parametrize("url,is_settled", [
    ("/images/mine.jpg", True),
    ("https://assets.tcgdex.net/en/sv/sv08.5/1/high.png", True),
    ("https://images.pokemontcg.io/base1/4.png", False),
    (None, False),
    ("", False),
])
def test_settled(url, is_settled):
    assert settled(url) is is_settled


def _seed_cards_module():
    """The seed script, which ships at /seed rather than on the import path."""
    import importlib.util

    path = Path("/seed/seed_cards.py")
    if not path.exists():
        pytest.skip("seed scripts not present (running outside the container)")
    spec = importlib.util.spec_from_file_location("seed_cards", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_weekly_refresh_does_not_undo_the_backfill(db, set_code, tmp_path):
    """The refresh re-reads the dump, which says images.pokemontcg.io for
    every card. If it wrote that back it would quietly return the whole
    catalogue to the other CDN and nothing would look wrong."""
    seed_cards = _seed_cards_module()

    moved = TCGDEX.format("1")
    mine = "/images/my-charizard.jpg"
    make_cards(db, set_code, [("1", moved), ("2", mine), ("3", None)])
    try:
        dump = tmp_path / f"{set_code}.json"
        dump.write_text(json.dumps([
            {
                "id": f"{set_code}-{n}",
                "name": f"Test Card {n}",
                "number": n,
                "rarity": "Common",
                "images": {"small": POKEMONTCG.format(set_code, n)},
            }
            for n in ("1", "2", "3")
        ]), encoding="utf-8")

        seed_cards.seed_file(db, dump, {set_code: {"name": "ZZ Test Set"}})
        db.expire_all()
        got = urls(db, set_code)

        assert got["1"] == moved, "the refresh put a moved card back on the old CDN"
        assert got["2"] == mine, "the refresh overwrote a collector's own photo"
        assert got["3"] == POKEMONTCG.format(set_code, 3), \
            "a card with no picture should still get one from the dump"
    finally:
        cleanup(db, set_code)
