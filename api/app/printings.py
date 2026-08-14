"""The ways a card was printed, in the words the set's own booklet uses.

Every Pokémon set ships with a card list, and beside each card is a row of
coloured boxes — one per printing — plus a rarity symbol. That booklet is the
model here, because it is the thing collectors already tick off.

    ☐ standard set                    ● common
    ☐ standard set foil               ◆ uncommon
    ☐ parallel set                    ★ rare
    ☐ premium parallel — Poké Ball    ★★ double rare
    ☐ premium parallel — Master Ball  …

TCGdex describes the same printings with three fields — `type`, `foil` and
`stamp` — and they line up exactly: a plain `reverse` is the parallel set, a
`reverse` with `foil: pokeball` is the Poké Ball parallel. What it does not
give is a short name, and a binder slot has twenty characters to store one in,
so the codes below are ours.

The count matters more than it sounds. Folding the three parallels into one
"reverse" cost Prismatic Evolutions 167 of its 476 printings, and a master set
that undercounts tells you that you have finished when you have not.
"""

# A printing is a combination, not a name from a list — kind, then whether it
# is foiled or stamped, then whether it is one of the oversized cards. So the
# code and the label are both built from the parts. Enumerating every
# combination was the first attempt and it silently dropped the four jumbo
# cards in Prismatic Evolutions, because nobody had thought to list them.
KIND_LABEL = {"normal": "Standard set", "reverse": "Parallel set", "holo": "Holo"}
KIND_CODE = {"normal": "n", "reverse": "r", "holo": "h"}

FOIL_LABEL = {
    "pokeball": "Poké Ball", "masterball": "Master Ball",
    "cosmos": "cosmos foil", "gold": "gold foil",
}
FOIL_CODE = {"pokeball": "pb", "masterball": "mb", "cosmos": "cos", "gold": "gold"}
FOIL_SHORT = {"pokeball": "P.BALL", "masterball": "M.BALL", "cosmos": "COS", "gold": "GOLD"}

STAMP_LABEL = {
    "set-logo": "set-logo stamp", "snowflake": "snowflake stamp",
    "30th-pokeday": "30th Pokéday stamp",
}
STAMP_CODE = {"set-logo": "logo", "snowflake": "snow", "30th-pokeday": "30th"}
STAMP_SHORT = {"set-logo": "LOGO", "snowflake": "SNOW", "30th-pokeday": "30TH"}

# what a premium parallel is called on the checklist, where it is its own line
PREMIUM = {"pokeball", "masterball"}


def _slug(value: str, n: int = 6) -> str:
    """A short, stable code for something nobody has named yet.

    Six characters, because a code has twenty to live in and may have to hold
    a kind, a foil, a stamp and a size at once.
    """
    keep = "".join(ch for ch in (value or "").lower() if ch.isalnum())
    return keep[:n] or "x"


def _humanise(value: str) -> str:
    return (value or "").replace("-", " ").replace("_", " ").strip()


def _parts(kind, foil, stamps, size):
    foil = (foil or "").lower() or None
    # any stamp, not only the ones already named: a printing we cannot name is
    # still a printing, and merging it into the plain one loses a slot
    stamp = next(iter(stamps or []), None)
    jumbo = (size or "").lower() == "jumbo"
    return (kind or "holo").lower(), foil, stamp, jumbo


def code_for(kind=None, foil=None, stamps=None, size=None) -> str:
    """One short name for a whole printing.

    Twenty characters, because that is what a binder slot key holds. The
    longest real combination is a stamped jumbo holo, which comes to ten.
    """
    kind, foil, stamp, jumbo = _parts(kind, foil, stamps, size)
    out = KIND_CODE.get(kind, "h")
    if foil:
        out += f"-{FOIL_CODE.get(foil) or _slug(foil)}"
    if stamp:
        out += f"-{STAMP_CODE.get(stamp) or _slug(stamp)}"
    if jumbo:
        out += "-jmb"
    return out


def label_for(kind=None, foil=None, stamps=None, size=None) -> str:
    """What the checklist would call it."""
    kind, foil, stamp, jumbo = _parts(kind, foil, stamps, size)
    if foil in PREMIUM:
        base = f"Premium parallel — {FOIL_LABEL[foil]}"
    else:
        base = KIND_LABEL.get(kind, "Holo")
        if foil:
            base += f", {FOIL_LABEL.get(foil) or _humanise(foil) + ' foil'}"
    stamp_label = STAMP_LABEL.get(stamp) or (f"{_humanise(stamp)} stamp" if stamp else None)
    extra = [x for x in (stamp_label, "jumbo" if jumbo else None) if x]
    return base + (", " + ", ".join(extra) if extra else "")


def short_for(kind=None, foil=None, stamps=None, size=None) -> str:
    """What fits beside a card number in a grid. The standard print gets
    nothing — it is the one you assume, and a label on it would be noise."""
    kind, foil, stamp, jumbo = _parts(kind, foil, stamps, size)
    bits = []
    if foil:
        bits.append(FOIL_SHORT.get(foil) or _slug(foil, 6).upper())
    elif kind == "reverse":
        bits.append("PAR")
    elif kind == "holo":
        bits.append("HOLO")
    if stamp:
        bits.append(STAMP_SHORT.get(stamp) or _slug(stamp, 6).upper())
    if jumbo:
        bits.append("JUMBO")
    return " ".join(bits)


# Codes are stored, so the binder has to turn one back into words without the
# parts that made it. Built once, from the same functions, so the two can
# never disagree.
def _all_codes():
    out = {}
    for kind in KIND_CODE:
        for foil in (None, *FOIL_CODE):
            for stamp in (None, *STAMP_CODE):
                for size in (None, "jumbo"):
                    st = [stamp] if stamp else []
                    out[code_for(kind, foil, st, size)] = (
                        label_for(kind, foil, st, size),
                        short_for(kind, foil, st, size),
                    )
    return out


PRINTINGS = _all_codes()


def label(code: str) -> str:
    return PRINTINGS.get(code, (code, code))[0]


def short(code: str) -> str:
    return PRINTINGS.get(code, (code, code))[1]


# --- rarity ---------------------------------------------------------------
#
# The symbols the booklet prints, as (glyph, tone). Tone is a colour name the
# stylesheet knows rather than a hex, so the palette stays in one place.
#
# Two of these are worth flagging: a double rare and an ultra rare are both
# two stars and differ only in colour on the card itself, which is exactly how
# they are told apart here.
RARITY = {
    "common":                    ("●", "plain"),
    "uncommon":                  ("◆", "plain"),
    "rare":                      ("★", "plain"),
    "double rare":               ("★★", "plain"),
    "ultra rare":                ("★★", "silver"),
    "illustration rare":         ("★", "gold"),
    "special illustration rare": ("★★", "gold"),
    "hyper rare":                ("★★★", "gold"),
    "ace spec rare":             ("★", "pink"),
    "shiny rare":                ("★", "silver"),
    "shiny ultra rare":          ("★★", "silver"),
    "radiant rare":              ("★", "gold"),
    "amazing rare":              ("★", "gold"),
    "promo":                     ("◈", "plain"),
}


def rarity_mark(rarity: str | None):
    """The printed symbol for a rarity, or nothing if we do not know it.

    Unknown rarities fall back to no symbol rather than a guessed one — an
    invented mark beside a real one is worse than a blank.
    """
    if not rarity:
        return None
    got = RARITY.get(rarity.strip().lower())
    if not got:
        return None
    glyph, tone = got
    return {"glyph": glyph, "tone": tone, "name": rarity}
