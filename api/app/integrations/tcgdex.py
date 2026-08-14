"""TCGdex client — the fallback catalog for cards the offline dump lacks.

TCGdex (api.tcgdex.net) is an open, no-key Pokémon TCG API that carries sets
the pokemon-tcg-data dump hasn't picked up yet — notably brand-new promo sets
like MEP (Mega Evolution Promos).

Why not pokemon.com directly: it sits behind Imperva bot protection, so a
server-side fetch is refused. TCGdex publishes the same card data for exactly
this purpose.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx

API_URL = "https://api.tcgdex.net/v2/en"


class TCGdexClient:
    @staticmethod
    def _brief(c: dict) -> dict:
        return {
            "tcgdex_id": c.get("id"),
            "title": c.get("name"),
            "card_number": c.get("localId"),
            "set_id": (c.get("id") or "").rsplit("-", 1)[0],
            # image is a base URL: append quality + extension
            "image_url": f"{c['image']}/high.png" if c.get("image") else None,
        }

    @staticmethod
    def _num_eq(a: str | None, b: str | None) -> bool:
        """"173" == "173" == "0173"; keeps letter numbers (TG12) exact."""
        if not a or not b:
            return False
        return a.strip().lstrip("0").upper() == b.strip().lstrip("0").upper()

    def cards_in_set(self, set_id: str) -> list[dict]:
        resp = httpx.get(
            f"{API_URL}/sets/{set_id.strip().lower()}",
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return [self._brief(c) for c in resp.json().get("cards", [])]

    def search_cards(
        self,
        name: str | None = None,
        set_id: str | None = None,
        number: str | None = None,
        limit: int = 24,
    ) -> list[dict]:
        """Find cards by any combination of name, set and printed number.

        Filtering happens across the WHOLE result list before truncating —
        a common name like Eevee has hundreds of prints, so cutting first
        would hide the very card being looked for.
        """
        if set_id and not (name or "").strip():
            # know the set and number but not the name: read the set directly
            results = self.cards_in_set(set_id)
        else:
            resp = httpx.get(
                f"{API_URL}/cards",
                params={"name": (name or "").strip()},
                timeout=25,
                follow_redirects=True,
            )
            resp.raise_for_status()
            results = [self._brief(c) for c in resp.json()]

        if set_id:
            s = set_id.strip().lower()
            results = [r for r in results if s == (r["set_id"] or "").lower()]
        if number and number.strip():
            num = number.strip().split("/")[0]
            results = [r for r in results if self._num_eq(r["card_number"], num)]
        if name and (name or "").strip() and set_id and not number:
            n = name.strip().lower()
            results = [r for r in results if n in (r["title"] or "").lower()]

        return results[:limit]

    def get_card(self, card_id: str) -> dict:
        """Full detail for one card — set name, rarity, dex number, art."""
        resp = httpx.get(
            f"{API_URL}/cards/{card_id}", timeout=20, follow_redirects=True
        )
        resp.raise_for_status()
        d = resp.json()
        s = d.get("set") or {}
        dex = d.get("dexId") or []
        return {
            "tcgdex_id": d.get("id"),
            "title": d.get("name"),
            "card_number": d.get("localId"),
            "set_id": s.get("id"),
            "set_name": s.get("name"),
            "set_total": (s.get("cardCount") or {}).get("total"),
            "rarity": d.get("rarity"),
            "national_dex_no": dex[0] if dex else None,
            # brand-new sets often have no art yet — the UI falls back to a
            # photo the collector takes themselves
            "image_url": f"{d['image']}/high.png" if d.get("image") else None,
        }

    # --- printings, for master-set binders ---------------------------------

    def set_id_for(self, name: str, code: str | None = None) -> str | None:
        """Their id for a set we know by name.

        The two catalogues do not agree on set ids and only sometimes collide:
        Celebrations is `cel25` in both, while Prismatic Evolutions is
        `sv8pt5` in the dump and `sv08.5` here. The printed name is the one
        thing they do share, so that is what this matches on, with the code
        tried first for the sets where it happens to line up.
        """
        sets = httpx.get(f"{API_URL}/sets", timeout=20, follow_redirects=True)
        sets.raise_for_status()
        rows = sets.json()
        if code:
            for s in rows:
                if (s.get("id") or "").lower() == code.lower():
                    return s["id"]
        want = (name or "").strip().casefold()
        for s in rows:
            if (s.get("name") or "").strip().casefold() == want:
                return s["id"]
        return None

    def printings_in_set(self, set_id: str, workers: int = 8) -> dict[str, dict]:
        """Every card's printings, keyed by its printed number.

        One request per card — the set listing carries only id, name, number
        and image — so it runs on a small pool over one connection. A set is
        180-odd cards and this is asked once, the first time somebody makes a
        master binder of it.
        """
        listing = httpx.get(
            f"{API_URL}/sets/{set_id.strip()}", timeout=20, follow_redirects=True
        )
        listing.raise_for_status()
        cards = listing.json().get("cards", [])

        out: dict[str, dict] = {}
        limits = httpx.Limits(max_connections=workers)
        with httpx.Client(timeout=20, follow_redirects=True, limits=limits) as client:
            def one(card):
                try:
                    r = client.get(f"{API_URL}/cards/{card['id']}")
                    r.raise_for_status()
                    return card.get("localId"), r.json().get("variants") or {}
                except Exception:
                    # one card the API stumbles on must not cost the whole set
                    return card.get("localId"), None

            with ThreadPoolExecutor(max_workers=workers) as pool:
                for number, variants in pool.map(one, cards):
                    if number and variants is not None:
                        out[str(number)] = variants
        return out


tcgdex_client = TCGdexClient()
