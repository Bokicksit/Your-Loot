"""What a card goes for right now, looked up on the spot and kept nowhere.

This is the price check on a binder page: switch it on, every card on the
page gets a market price laid over it, switch it off and it is gone. Nothing
is written to the database on purpose. A price is a fact about this
afternoon, and a table of them is a table of things that used to be true —
the barcode cache next door can keep its answers forever because a barcode
does not change its mind; a price does, daily, and stored it would be shown
as current long after it stopped being so.

The numbers come from TCGdex, which already supplies this app's card art and
carries live TCGplayer figures on every card. Dollars only — see pick(). Not
eBay: eBay does not sell its sold-listings data to anybody this size. What
TCGplayer publishes as its market price is derived from actual completed
sales on the largest singles marketplace there is, which is the same
question answered from a cleaner source. It is shown with its name on it so
nobody mistakes it for an appraisal.

Two things make it cheap enough to do live. A page is nine cards, so a check
is nine small requests in parallel and lands in well under a second. And the
only cache is in memory and short — a few minutes — so flipping between two
pages does not ask the same question twice, without anything surviving a
restart.

Ids need care. Most of the catalogue was seeded from a different dump whose
card ids agree with TCGdex's for older sets (`base1-4` is `base1-4` in both)
and disagree for modern ones (`sv3pt5` there, `sv03.5` here). Rather than
guess, an id that fails is resolved the way the rest of this app already
does it — by set name, then by printed number within the set listing — so
a card is priced wherever the two catalogues can be made to agree, and shown
without a price where they cannot.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.integrations.tcgdex import tcgdex_client

# How long an answer is reused. Long enough that paging back and forth is
# free, short enough that nobody is ever shown yesterday.
PRICE_TTL = 5 * 60
# Set listings change only when a set is released, so these can sit longer.
SETS_TTL = 60 * 60
# A page is nine cards; a spread is eighteen. This is the most one check may
# ask for, so the endpoint cannot be used to walk the whole catalogue.
MAX_CARDS = 40
# Parallel requests per check. TCGdex has no published limit; this is polite.
WORKERS = 8

# The copy's variant, as this app records it, against the keys TCGplayer
# uses for the same printing. Loose on purpose: TCGplayer's names vary by
# era ("holofoil", "1st-edition-holofoil", "unlimited-holofoil").
_WANT = {
    "reverse holo": ("reverse",),
    "holo": ("holofoil", "holo"),
    "non-holo": ("normal", "unlimited"),
}


class _Memo:
    """A dict with an expiry on every key. In memory, and meant to be."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._d: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._d.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
            self._d.pop(key, None)
            return None

    def put(self, key, value):
        with self._lock:
            self._d[key] = (time.monotonic() + self.ttl, value)

    def clear(self):
        with self._lock:
            self._d.clear()


prices = _Memo(PRICE_TTL)
sets = _Memo(SETS_TTL)
listings = _Memo(SETS_TTL)

# When the provider stops answering, say so at once rather than making nine
# cards each wait out a timeout. One failed connection marks it down for a
# minute; every check in that minute is refused instantly and the page says
# the service is unavailable. It came from watching TCGdex go dark for half
# an hour mid-build: a free API with no SLA is a thing that happens, and a
# page that hangs for twenty seconds before admitting it is worse than one
# that says so in twenty milliseconds.
DOWN_FOR = 60
_down_until = 0.0
_down_lock = threading.Lock()


class ProviderDown(httpx.HTTPError):
    """Raised without a request when the provider was recently unreachable."""


def _gate():
    if time.monotonic() < _down_until:
        raise ProviderDown("price provider is down")


def _mark_down():
    global _down_until
    with _down_lock:
        _down_until = time.monotonic() + DOWN_FOR


def pick(pricing: dict | None, variant: str | None) -> dict | None:
    """One price for the card, from everything TCGdex reports for it.

    TCGplayer, in dollars, for the printing that matches the copy — a
    reverse holo and a plain print of the same card are different prices and
    the copy knows which it is. Failing a match, any TCGplayer variant with a
    market price. Nothing at all means the card is not on TCGplayer, which is
    an answer too, and the caller shows a dash rather than a zero.

    Dollars only, and not as a fallback order but as a rule: TCGdex also
    carries Cardmarket in euros, and it is deliberately ignored. A page total
    is one number, and a number summed across two currencies is not a total
    of anything. Where a card is on Cardmarket and not on TCGplayer it gets a
    dash, the same as a card on neither.
    """
    if not pricing:
        return None
    tp = pricing.get("tcgplayer") or {}
    variants = {
        k: v for k, v in tp.items()
        if isinstance(v, dict) and v.get("marketPrice") is not None
    }
    if variants:
        want = _WANT.get((variant or "").strip().lower(), ())
        chosen = None
        for key in variants:
            k = key.lower()
            if any(w in k for w in want) and not (
                "reverse" in k and "reverse" not in want
            ):
                chosen = key
                break
        if chosen is None:
            # the plain print is the usual one when the copy says nothing
            for key in variants:
                if "normal" in key.lower() or "unlimited" in key.lower():
                    chosen = key
                    break
        if chosen is None:
            chosen = next(iter(variants))
        v = variants[chosen]
        return {
            "amount": float(v["marketPrice"]),
            "currency": "USD",
            "low": v.get("lowPrice"),
            "high": v.get("highPrice"),
            "variant": chosen,
            "source": "TCGplayer",
            "updated": tp.get("updated"),
        }
    return None


def _sets():
    rows = sets.get("all")
    if rows is None:
        _gate()
        try:
            rows = tcgdex_client.all_sets()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            _mark_down()
            raise
        sets.put("all", rows)
    return rows


def _listing(set_id: str) -> list[dict]:
    rows = listings.get(set_id)
    if rows is None:
        _gate()
        try:
            rows = tcgdex_client.cards_in_set(set_id)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            _mark_down()
            raise
        listings.put(set_id, rows)
    return rows


def resolve(card) -> str | None:
    """TCGdex's id for one of our cards, or None where the two catalogues
    cannot be made to agree.

    `card` is anything with `source`, `external_id`, `set_code`, `set_name`
    and `card_number`. Cards imported from TCGdex carry its id already. Cards
    from the dump usually carry an id TCGdex also understands; when it does
    not, the set is found by name and the card by its printed number, which
    is the one thing both catalogues print on the card itself.
    """
    if card.source in ("tcgdex", "tcgdex-ja") and card.external_id:
        return card.external_id
    if card.source == "ptcg" and card.external_id:
        # try the id as-is first; for most of the catalogue it simply works
        return card.external_id
    return None


def resolve_by_set(card) -> str | None:
    """The slow path: set name, then printed number within the set."""
    if not card.set_name or not card.card_number:
        return None
    set_id = tcgdex_client.set_id_for(card.set_name, card.set_code, sets=_sets())
    if not set_id:
        return None
    num = str(card.card_number).split("/")[0]
    for row in _listing(set_id):
        if tcgdex_client._num_eq(row.get("card_number"), num):
            return row.get("tcgdex_id")
    return None


def _fetch(tcgdex_id: str) -> dict | None:
    """The raw pricing block for one TCGdex id, or None. 404 is a real answer
    (the id is not theirs); anything else is a failure worth telling about."""
    hit = prices.get(tcgdex_id)
    if hit is not None:
        return hit or None
    _gate()
    try:
        r = httpx.get(
            f"https://api.tcgdex.net/v2/en/cards/{tcgdex_id}",
            timeout=6, follow_redirects=True,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        _mark_down()
        raise
    if r.status_code == 404:
        prices.put(tcgdex_id, {})
        return None
    r.raise_for_status()
    block = r.json().get("pricing") or {}
    prices.put(tcgdex_id, block)
    return block or None


def check(cards: list, variants: dict[int, str | None] | None = None) -> dict:
    """Price a handful of cards. Returns {item_id: price-or-None} plus a note
    on how it went, so the page can say "7 of 9" rather than pretend.

    `cards` are ORM items with card_attrs loaded. `variants` maps item id to
    the copy's variant, where the caller knows it.
    """
    variants = variants or {}
    out: dict[int, dict | None] = {}
    failed = False

    def one(item):
        a = item.card_attrs
        shim = type("C", (), {
            "source": item.source, "external_id": item.external_id,
            "set_code": a.set_code if a else None,
            "set_name": a.set_name if a else None,
            "card_number": a.card_number if a else None,
        })()
        try:
            tid = resolve(shim)
            block = _fetch(tid) if tid else None
            if block is None:
                # the id was not theirs (or we had none): try the set route
                alt = resolve_by_set(shim)
                if alt and alt != tid:
                    block = _fetch(alt)
            return item.id, pick(block, variants.get(item.id)), False
        except (httpx.HTTPError, ValueError):
            return item.id, None, True

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for item_id, price, err in pool.map(one, cards[:MAX_CARDS]):
            out[item_id] = price
            failed = failed or err

    priced = sum(1 for v in out.values() if v)
    return {
        "prices": out,
        "priced": priced,
        "asked": len(out),
        # true when the provider itself failed, as distinct from a card that
        # simply has no price — the page says different things for each
        "unavailable": failed and priced == 0,
    }
