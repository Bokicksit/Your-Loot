"""The price check, with the network taken out.

What TCGdex sends back is a nest of marketplaces and printings, and the one
figure a card shows has to be chosen from it the same way every time: the
copy's own printing when there is one, the plain print when the copy says
nothing, dollars before euros, and a dash — never a zero — when the card is
on no marketplace at all. Those choices are the feature; the HTTP is not.

    docker compose -f compose.test.yaml run --rm tests
"""

import sys

import pytest

sys.path.insert(0, "/app")

from app import prices  # noqa: E402

# a real answer, trimmed: Base Set Charizard as TCGdex reports it
CHARIZARD = {
    "cardmarket": {
        "updated": "2026-09-01T09:33:39.806Z", "unit": "EUR",
        "avg": 487.19, "low": 99.89, "trend": 626.31,
        "avg1": 349, "avg7": 992.93, "avg30": 561.1,
    },
    "tcgplayer": {
        "unit": "USD", "updated": "2026-09-01T09:33:40.669Z",
        "holofoil": {"lowPrice": 120.0, "midPrice": 300.0, "highPrice": 3000.0,
                     "marketPrice": 285.5, "directLowPrice": None},
        "1st-edition-holofoil": {"lowPrice": 900.0, "midPrice": 2500.0,
                                 "highPrice": 20000.0, "marketPrice": 2400.0},
    },
}

# a modern common with the three usual printings
EEVEE = {
    "tcgplayer": {
        "unit": "USD", "updated": "2026-09-01T09:00:00Z",
        "normal": {"lowPrice": 0.05, "midPrice": 0.2, "highPrice": 2.0, "marketPrice": 0.12},
        "reverse-holofoil": {"lowPrice": 0.2, "midPrice": 0.5, "highPrice": 4.0, "marketPrice": 0.41},
        "holofoil": {"lowPrice": 1.0, "midPrice": 3.0, "highPrice": 9.0, "marketPrice": 2.3},
    },
}


@pytest.fixture(autouse=True)
def forget():
    prices.prices.clear()
    prices.sets.clear()
    prices.listings.clear()
    prices._down_until = 0.0
    yield
    prices._down_until = 0.0


# ----------------------------------------------------------- which figure

def test_the_copy_s_own_printing_is_the_one_priced():
    assert prices.pick(EEVEE, "Reverse Holo")["amount"] == 0.41
    assert prices.pick(EEVEE, "Holo")["amount"] == 2.3
    assert prices.pick(EEVEE, "Non-Holo")["amount"] == 0.12


def test_a_copy_that_says_nothing_gets_the_plain_print():
    """Most copies record no variant; the ordinary print is what they are."""
    assert prices.pick(EEVEE, None)["amount"] == 0.12
    assert prices.pick(EEVEE, "")["variant"] == "normal"


def test_holo_does_not_accidentally_match_reverse_holo():
    """Both keys contain "holo"; only one of them is the card in the slot."""
    assert prices.pick(EEVEE, "Holo")["variant"] == "holofoil"


def test_a_card_with_only_holo_printings_still_prices():
    """Charizard has no "normal": asking for the plain print must not come
    back empty-handed when the card was never printed plain."""
    p = prices.pick(CHARIZARD, None)
    assert p is not None
    assert p["source"] == "TCGplayer"
    assert p["currency"] == "USD"
    # not the 1st edition — that is a different card to a buyer
    assert p["amount"] == 285.5


def test_dollars_come_before_euros_but_euros_beat_nothing():
    assert prices.pick(CHARIZARD, "Holo")["currency"] == "USD"
    only_eu = {"cardmarket": CHARIZARD["cardmarket"]}
    p = prices.pick(only_eu, None)
    assert p["currency"] == "EUR"
    assert p["amount"] == 626.31  # the trend, not the raw average
    assert p["source"] == "Cardmarket"


def test_no_marketplace_means_no_price_not_zero():
    """A dash on the card and left out of the total; a zero would be a lie
    that also lowers the page."""
    assert prices.pick(None, None) is None
    assert prices.pick({}, None) is None
    assert prices.pick({"tcgplayer": {"unit": "USD"}}, None) is None
    assert prices.pick({"tcgplayer": {"normal": {"marketPrice": None}}}, None) is None


def test_the_range_travels_with_the_figure():
    p = prices.pick(CHARIZARD, "Holo")
    assert (p["low"], p["high"]) == (120.0, 3000.0)
    assert p["updated"] == "2026-09-01T09:33:40.669Z"


# ------------------------------------------------------------ which card

class Card:
    def __init__(self, **kw):
        self.source = kw.get("source")
        self.external_id = kw.get("external_id")
        self.set_code = kw.get("set_code")
        self.set_name = kw.get("set_name")
        self.card_number = kw.get("card_number")


def test_our_ids_are_tried_as_theirs_first():
    """For most of the catalogue the ids simply agree, and a lookup is one
    request with no set listing involved."""
    assert prices.resolve(Card(source="ptcg", external_id="base1-4")) == "base1-4"
    assert prices.resolve(Card(source="tcgdex", external_id="sv03.5-001")) == "sv03.5-001"


def test_a_hand_made_card_has_nothing_to_look_up():
    assert prices.resolve(Card(source="manual", external_id=None)) is None


def test_the_set_route_matches_by_name_then_printed_number(monkeypatch):
    """Where the ids disagree — every Scarlet & Violet set — the set is found
    by its printed name and the card by its number, which is what the two
    catalogues actually share."""
    monkeypatch.setattr(prices.tcgdex_client, "all_sets",
                        lambda: [{"id": "sv03.5", "name": "151"}])
    monkeypatch.setattr(prices.tcgdex_client, "cards_in_set", lambda sid: [
        {"tcgdex_id": "sv03.5-001", "card_number": "001"},
        {"tcgdex_id": "sv03.5-199", "card_number": "199"},
    ])
    card = Card(source="ptcg", external_id="sv3pt5-199",
                set_code="sv3pt5", set_name="151", card_number="199/165")
    assert prices.resolve_by_set(card) == "sv03.5-199"


def test_the_set_listing_is_asked_for_once(monkeypatch):
    """Nine cards from one set is one listing, not nine."""
    calls = []
    monkeypatch.setattr(prices.tcgdex_client, "all_sets",
                        lambda: [{"id": "sv03.5", "name": "151"}])

    def listing(sid):
        calls.append(sid)
        return [{"tcgdex_id": f"sv03.5-{n:03d}", "card_number": f"{n:03d}"}
                for n in range(1, 10)]

    monkeypatch.setattr(prices.tcgdex_client, "cards_in_set", listing)
    for n in range(1, 10):
        prices.resolve_by_set(Card(source="ptcg", set_name="151",
                                   set_code="sv3pt5", card_number=str(n)))
    assert calls == ["sv03.5"]


# --------------------------------------------------------------- the check

class Item:
    def __init__(self, id, source, external_id, variant=None, **attrs):
        self.id = id
        self.source = source
        self.external_id = external_id
        self.card_attrs = type("A", (), {
            "set_code": attrs.get("set_code"),
            "set_name": attrs.get("set_name"),
            "card_number": attrs.get("card_number"),
        })()


def test_a_page_is_priced_together_and_counted_honestly(monkeypatch):
    answers = {"base1-4": CHARIZARD, "base1-5": EEVEE, "base1-6": {}}
    monkeypatch.setattr(prices, "_fetch", lambda tid: answers.get(tid) or None)
    monkeypatch.setattr(prices, "resolve_by_set", lambda c: None)
    items = [Item(1, "ptcg", "base1-4"), Item(2, "ptcg", "base1-5"),
             Item(3, "ptcg", "base1-6"), Item(4, "manual", None)]
    out = prices.check(items, {2: "Reverse Holo"})
    assert out["asked"] == 4
    assert out["priced"] == 2
    assert out["prices"][1]["amount"] == 285.5
    assert out["prices"][2]["amount"] == 0.41  # the copy's variant, per card
    assert out["prices"][3] is None
    assert out["prices"][4] is None
    assert out["unavailable"] is False


def test_the_provider_being_down_is_said_not_shown_as_dashes(monkeypatch):
    """Every card coming back blank because TCGdex is unreachable is a
    different fact from every card being unlisted, and the page must be able
    to tell them apart."""
    import httpx

    def down(tid):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(prices, "_fetch", down)
    out = prices.check([Item(1, "ptcg", "base1-4"), Item(2, "ptcg", "base1-5")])
    assert out["priced"] == 0
    assert out["unavailable"] is True


def test_no_more_than_a_spread_is_priced_at_once(monkeypatch):
    seen = []
    monkeypatch.setattr(prices, "_fetch", lambda tid: seen.append(tid) or None)
    monkeypatch.setattr(prices, "resolve_by_set", lambda c: None)
    items = [Item(n, "ptcg", f"x-{n}") for n in range(100)]
    prices.check(items)
    assert len(seen) == prices.MAX_CARDS


def test_the_memo_forgets_on_time(monkeypatch):
    m = prices._Memo(ttl=10)
    now = [1000.0]
    monkeypatch.setattr(prices.time, "monotonic", lambda: now[0])
    m.put("k", {"a": 1})
    assert m.get("k") == {"a": 1}
    now[0] += 11
    assert m.get("k") is None


# ------------------------------------------------------------ when it is down

def test_one_dead_connection_stops_the_rest_from_waiting(monkeypatch):
    """Nine cards, one timeout: the other eight must not each sit through
    their own. The first failure marks the provider down and the rest are
    refused on the spot."""
    import httpx

    calls = []

    def get(url, **kw):
        calls.append(url)
        raise httpx.ConnectTimeout("no route")

    monkeypatch.setattr(prices.httpx, "get", get)
    monkeypatch.setattr(prices, "resolve_by_set", lambda c: None)
    monkeypatch.setattr(prices, "WORKERS", 1)  # so the order is deterministic
    out = prices.check([Item(n, "ptcg", f"base1-{n}") for n in range(1, 10)])
    assert out["unavailable"] is True
    assert len(calls) == 1  # one real attempt; eight refused without asking


def test_the_provider_is_tried_again_after_a_minute(monkeypatch):
    now = [5000.0]
    monkeypatch.setattr(prices.time, "monotonic", lambda: now[0])
    prices._mark_down()
    with pytest.raises(prices.ProviderDown):
        prices._gate()
    now[0] += prices.DOWN_FOR + 1
    prices._gate()  # no longer raises


def test_a_cached_price_is_served_even_while_the_provider_is_down(monkeypatch):
    """Down means "do not ask", not "forget what you know"."""
    prices.prices.put("base1-4", CHARIZARD)
    prices._mark_down()
    assert prices._fetch("base1-4") == CHARIZARD
