"""Card classification shared by the API and the seed script."""

import re


def classify_layer(rarity: str | None) -> int:
    """Binder layer by card *style*, era-agnostic:
    3 = IR / SIR / alt-illustration styles
    2 = full-art (SV ex Ultra Rare, V/VMAX/VSTAR/GX/EX full arts, rainbows)
    1 = everything else: commons/uncommons/holos, regular ex (Double Rare),
        vintage cards, and gold Hyper Rares / Secrets
    """
    r = (rarity or "").lower()
    if "illustration" in r or "trainer gallery" in r:
        return 3
    if (
        "ultra" in r
        or "full art" in r
        or "rainbow" in r
        or re.search(r"holo (v|vmax|vstar|gx|ex|lv\.x)\b", r)
    ):
        return 2
    return 1


def derive_variant(rarity: str | None) -> str:
    """Print style implied by the catalog rarity (a copy can override it)."""
    r = (rarity or "").lower()
    if "full art" in r or "ultra" in r:
        return "full-art"
    if "holo" in r:
        return "holo"
    return "normal"
