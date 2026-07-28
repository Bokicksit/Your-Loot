"""TCGdex client — the fallback catalog for cards the offline dump lacks.

TCGdex (api.tcgdex.net) is an open, no-key Pokémon TCG API that carries sets
the pokemon-tcg-data dump hasn't picked up yet — notably brand-new promo sets
like MEP (Mega Evolution Promos).

Why not pokemon.com directly: it sits behind Imperva bot protection, so a
server-side fetch is refused. TCGdex publishes the same card data for exactly
this purpose.
"""

import httpx

API_URL = "https://api.tcgdex.net/v2/en"


class TCGdexClient:
    def search_cards(self, name: str, limit: int = 20) -> list[dict]:
        """Brief search — id encodes set+number ("mep-009")."""
        resp = httpx.get(
            f"{API_URL}/cards",
            params={"name": name.strip()},
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        out = []
        for c in resp.json()[:limit]:
            set_id = (c.get("id") or "").rsplit("-", 1)[0]
            out.append({
                "tcgdex_id": c.get("id"),
                "title": c.get("name"),
                "card_number": c.get("localId"),
                "set_id": set_id,
                # image is a base URL: append quality + extension
                "image_url": f"{c['image']}/high.png" if c.get("image") else None,
            })
        return out

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


tcgdex_client = TCGdexClient()
