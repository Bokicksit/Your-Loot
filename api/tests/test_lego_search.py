"""Which LEGO sets a name search should offer first.

Rebrickable answers a name search in set-number order, which is no order at
all to a person, and its catalogue includes the LEGO *video games* alongside
the sets. Searching "nintendo" returns thirty-five things, seventeen of them
Switch titles with no bricks in them, and the Nintendo Entertainment System
— the actual 2,646-piece set — is not in the first twenty by set number. So
the app ranks them itself; this is that ranking.

Pure functions and no network: the ordering is the part that was wrong, and
it can be proven with a handful of rows that look like what came back.

    docker compose -f compose.test.yaml run --rm tests
"""

import sys

sys.path.insert(0, "/app")

from app.integrations.rebrickable import _rank, _relevance  # noqa: E402


def _set(name, parts, year=2020, num="1-1"):
    return {"name": name, "num_parts": parts, "year": year, "set_num": num}


def order(rows, term):
    return [s["name"] for s in sorted(rows, key=lambda s: _rank(s, term))]


def test_a_set_you_can_build_comes_before_a_video_game():
    """The whole complaint, in one assertion. Both of these match "nintendo";
    only one of them is a box of bricks."""
    rows = [
        _set("Marvel Super Heroes 2 - Nintendo Switch", 0),
        _set("The Incredibles - Nintendo Switch", 0),
        _set("Nintendo Entertainment System", 2646),
    ]
    assert order(rows, "nintendo")[0] == "Nintendo Entertainment System"


def test_the_game_boy_is_found_among_its_own_video_games():
    """Nineteen results for "game boy" and exactly one has pieces in it."""
    rows = [
        _set("Bionicle: Maze of Shadows - Game Boy Advance", 0),
        _set("Game Boy", 421, year=2025),
        _set("Drome Racers - Game Boy Advance", 0),
    ]
    assert order(rows, "game boy")[0] == "Game Boy"


def test_a_video_game_is_ranked_last_rather_than_hidden():
    """Being unfindable is its own bug, and the catalogue is not ours to
    censor — a search for something with no bricks still finds it, last."""
    rows = [_set("Bionicle Heroes - Game Boy Advance", 0), _set("Game Boy", 421)]
    assert order(rows, "game boy")[-1] == "Bionicle Heroes - Game Boy Advance"


def test_the_big_set_comes_before_the_small_one():
    """Searching a theme should offer the display piece before the keyring."""
    rows = [
        _set("Millennium Falcon", 1330, year=2015),
        _set("Millennium Falcon", 7541, year=2017),
        _set("Millennium Falcon", 1254, year=2011),
    ]
    assert [s["num_parts"] for s in sorted(rows, key=lambda s: _rank(s, "millennium falcon"))] == [
        7541, 1330, 1254,
    ]


def test_an_exact_name_beats_a_longer_one_that_contains_it():
    rows = [_set("Bonsai Tree", 878), _set("Japanese Red Maple Bonsai Tree", 474)]
    assert order(rows, "bonsai tree")[0] == "Bonsai Tree"


def test_relevance_reads_a_name_the_way_a_person_would():
    # exact, then the name starting with it, then the words in it, then
    # buried inside a longer word
    assert _relevance("Titanic", "titanic") == 0
    assert _relevance("Nintendo Entertainment System", "nintendo") == 1
    assert _relevance("Marvel Super Heroes 2 - Nintendo Switch", "nintendo") == 2
    assert _relevance("Retro Console Kit", "nintendo") == 4
    # punctuation is a gap between words, so a term beside a dash still counts
    # as one — this is why the test above scores 2 rather than 3
    assert _relevance("Star Wars II - Game Boy Advance", "game boy") == 2
