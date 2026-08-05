"""Text-matching helpers shared by every collection's search."""

from sqlalchemy import func


def contains(column, term: str):
    """Accent- and case-insensitive "contains" match.

    ILIKE folds case but not accents, so "pokemon catcher" missed "Pokémon
    Catcher" and "flabebe" missed "Flabébé" — 430 cards in the dump carry a
    diacritic, and é isn't on a phone keyboard. Unaccenting BOTH sides also
    means someone who does type the accent still finds the card.

    It deliberately leaves ♂ ♀ δ alone: those aren't accented letters, and
    they're separate tokens, so "Nidoran" already matches "Nidoran ♂".

    Not indexable (a leading-wildcard LIKE never was), and at this size a scan
    is instant.
    """
    return func.unaccent(column).ilike(func.unaccent(f"%{term}%"))


def starts_with(column, term: str):
    """Same, anchored at the start — for codes like set abbreviations."""
    return func.unaccent(column).ilike(func.unaccent(f"{term}%"))
