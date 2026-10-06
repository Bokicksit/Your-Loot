"""Which Pokémon LEGO has made, and in which sets.

Nobody publishes this as data — Rebrickable lists a set's parts, not its
species — so it is kept here by hand, from LEGO's own announcements. A new
wave is a few lines added below. A tile from a set not listed yet still
works: pairing takes any dex number, and the Pokémon joins the grid.

`tags` says whether the set comes with a Smart Tag for each of its Pokémon.
The 18+ display sets of February 2026 do not; their Pokémon can only be
captured by owning the set, when that is switched on.
"""

# (set number, name, dex numbers, has Smart Tags)
SETS = [
    ("72151", "Eevee", [133], False),
    ("72152", "Pikachu and Poké Ball", [25], False),
    ("72153", "Venusaur, Charizard and Blastoise", [3, 6, 9], False),
    ("72155", "Berry Bash with Bulbasaur and Bidoof", [1, 399], True),
    ("72156", "Trainer's Buggy Adventure with Squirtle", [7], True),
    ("72157", "Charmander and Geodude's Cavern Clash", [4, 74], True),
    ("72158", "Sprigatito, Fuecoco and Quaxly Battle", [906, 909, 912], True),
    ("72159", "Jigglypuff Concert", [39], True),
    ("72161", "Drone Search for Mythical Mew", [151], True),
    ("72162", "Eevee and Lapras's Treasure Hunt", [133, 131], True),
    ("72163", "Mewtwo's Lab Break", [150], True),
    ("72164", "Training House with Pikachu", [25], True),
    ("72165", "Umbreon vs. Garchomp Championship Battle", [197, 445], True),
    ("72166", "Cubone and Gengar's Spooky Showdown", [104, 94], True),
    ("72167", "Charizard vs. Jolteon Ultimate Battle", [6, 135], True),
    ("40887", "Ditto as Squirtle: Movie Night", [132], True),
]

# So the page has names without the card catalogue — somebody who collects
# LEGO and not cards may never have seeded it.
NAMES = {
    1: "Bulbasaur", 3: "Venusaur", 4: "Charmander", 6: "Charizard",
    7: "Squirtle", 9: "Blastoise", 25: "Pikachu", 39: "Jigglypuff",
    74: "Geodude", 94: "Gengar", 104: "Cubone", 131: "Lapras", 132: "Ditto",
    133: "Eevee", 135: "Jolteon", 150: "Mewtwo", 151: "Mew", 197: "Umbreon",
    399: "Bidoof", 445: "Garchomp", 906: "Sprigatito", 909: "Fuecoco",
    912: "Quaxly",
}


def set_key(number: str | None) -> str:
    """`72155-1` (Rebrickable's form) and `72155` are the same set."""
    return (number or "").strip().split("-")[0]
