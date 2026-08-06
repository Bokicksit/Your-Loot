"""Ordering helpers shared by the collection list endpoints.

Kept together because the awkward cases repeat: a year that only exists inside
the title, and numbers stored as text because half of them aren't numbers.
"""

from sqlalchemy import Integer, case, cast, func


def year_from_title(title_col):
    """`Blade Runner 2049 (2017)` -> 2017.

    Games and movies both carry their release year as a title suffix, and for
    films that's the only place it lives — there is no year column on
    movie_attrs. The pattern only ever matches four digits in trailing
    brackets, so the cast has nothing else to chew on.
    """
    return cast(func.substring(title_col, r"\(([0-9]{4})\)$"), Integer)


def leading_number(col):
    """`75192` -> 75192, `1A` -> 1, `½` -> NULL.

    Set numbers and issue numbers are text columns because plenty of them
    aren't numbers, but the ones that are should file the way a shelf does.
    Plain text ordering puts 10 before 9, which is wrong everywhere it shows.
    """
    return cast(func.substring(col, r"^([0-9]+)"), Integer)


def rarity_rank(col):
    """Commons first, secret rares last — the order the symbols are printed in,
    not the order the words fall in the alphabet, which would file Common
    between Rainbow and Ultra.

    Mirrors the tiers RarityMark draws, and in the same precedence: the first
    branch that matches wins, so "special illustration" has to be tested
    before "illustration".
    """
    low = func.lower(func.coalesce(col, ""))
    return case(
        (low == "common", 1),
        (low == "uncommon", 2),
        (low.like("%promo%"), 3),
        (low.like("%special illustration%"), 8),
        (low.like("%illustration%"), 7),
        (low.like("%hyper%"), 9),
        (low.like("%secret%"), 8),
        (low.like("%rainbow%"), 8),
        (low.like("%ultra%"), 6),
        (low.like("%double%"), 5),
        (low.like("%rare%"), 4),
        else_=0,
    )
