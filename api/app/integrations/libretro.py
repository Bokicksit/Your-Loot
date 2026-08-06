"""libretro-thumbnails — scans of the actual box, for the consoles that had one.

IGDB gives a game's key art: the same image whether you own the original, the
Player's Choice reprint or a download. This is a photograph of the front of the
box, which is what's actually on the shelf.

No API key and no account — it's a plain static file server. There's no search
endpoint either, and the filenames follow No-Intro conventions that can't be
guessed from a title: articles move to the end ("Legend of Zelda, The"), a
subtitle colon becomes " - ", and the server is case-sensitive. So instead of
guessing, each system's directory index is read once and matched against with
both sides flattened to the same shape.

Only covers systems old enough to have been archived — roughly NES through
Xbox 360. Anything newer falls back to IGDB art.
"""

import re
from urllib.parse import quote, unquote

import httpx

BASE = "https://thumbnails.libretro.com"

# our platform abbreviation -> the project's folder name
SYSTEMS = {
    "NES": "Nintendo - Nintendo Entertainment System",
    "SNES": "Nintendo - Super Nintendo Entertainment System",
    "N64": "Nintendo - Nintendo 64",
    "GCN": "Nintendo - GameCube",
    "GB": "Nintendo - Game Boy",
    "GBC": "Nintendo - Game Boy Color",
    "GBA": "Nintendo - Game Boy Advance",
    "NDS": "Nintendo - Nintendo DS",
    "3DS": "Nintendo - Nintendo 3DS",
    "Wii": "Nintendo - Wii",
    "WiiU": "Nintendo - Wii U",
    "PS1": "Sony - PlayStation",
    "PS2": "Sony - PlayStation 2",
    "PS3": "Sony - PlayStation 3",
    "PSP": "Sony - PlayStation Portable",
    "Vita": "Sony - PlayStation Vita",
    "GEN": "Sega - Mega Drive - Genesis",
    "DC": "Sega - Dreamcast",
    "XBOX": "Microsoft - Xbox",
    "X360": "Microsoft - Xbox 360",
}

# Which region tag to prefer for a given shelf. Falls through the rest, since
# most of the archive is filed under USA or World whatever you own.
REGIONS = {
    "NTSC-U": ["usa", "usa, europe", "world", "europe", "japan, usa", "japan"],
    "PAL": ["europe", "usa, europe", "world", "usa", "japan"],
    "NTSC-J": ["japan", "japan, usa", "world", "usa", "europe"],
}
DEFAULT_REGIONS = ["usa", "world", "usa, europe", "europe", "japan"]

# dumps that aren't the retail box
BAD_TAGS = ("beta", "proto", "demo", "sample", "unl", "pirate", "test program", "hack")

_ARTICLES = re.compile(r"\b(the|a|an)\b")
_PUNCT = re.compile(r"[^a-z0-9]+")
_YEAR_SUFFIX = re.compile(r"\s*\(\d{4}\)\s*$")
_TAGS = re.compile(r"\(([^)]*)\)")
_HREF = re.compile(r'href="([^"?][^"]*\.png)"', re.I)

_index_cache: dict[str, dict[str, list]] = {}


def _norm(title: str) -> str:
    """Flatten a title to something both sides agree on.

    Articles come out entirely rather than being moved, which is the cheap way
    to make "The Legend of Zelda" and "Legend of Zelda, The" the same key, and
    all punctuation goes with them so a colon, a dash and a comma stop
    mattering.
    """
    s = _YEAR_SUFFIX.sub("", title or "").lower()
    s = s.replace("&", " and ")
    s = _ARTICLES.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    return " ".join(s.split())


def _split(stem: str) -> tuple[str, list[str]]:
    """`Pokemon - Red Version (USA, Europe) (SGB Enhanced)` ->
    ("Pokemon - Red Version", ["usa, europe", "sgb enhanced"])"""
    tags = [t.strip().lower() for t in _TAGS.findall(stem)]
    return _TAGS.sub("", stem).strip(), tags


def _index(system: str) -> dict[str, list]:
    """Every box scan for one system, keyed by flattened title. One ~600KB
    read, then it's answered from memory for the life of the container."""
    if system in _index_cache:
        return _index_cache[system]
    url = f"{BASE}/{quote(system)}/Named_Boxarts/"
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
    out: dict[str, list] = {}
    for href in _HREF.findall(r.text):
        filename = unquote(href)
        base, tags = _split(filename[:-4])
        out.setdefault(_norm(base), []).append((filename, tags))
    _index_cache[system] = out
    return out


def _score(tags: list[str], region: str | None) -> int:
    joined = " ".join(tags)
    if any(b in joined for b in BAD_TAGS):
        return -1000
    prefs = REGIONS.get(region or "", DEFAULT_REGIONS)
    first = tags[0] if tags else ""
    rank = prefs.index(first) if first in prefs else len(prefs)
    # region first, then the plainest scan: "(USA)" beats "(USA) (Rev 1)"
    return -rank * 10 - len(tags)


def boxart(title: str, platform_abbr: str | None, region: str | None = None) -> str | None:
    """URL of the best box scan for this game, or None."""
    system = SYSTEMS.get(platform_abbr or "")
    if not system:
        return None
    try:
        index = _index(system)
    except httpx.HTTPError:
        return None
    hits = index.get(_norm(title))
    if not hits:
        return None
    filename, tags = max(hits, key=lambda h: _score(h[1], region))
    if _score(tags, region) <= -1000:
        return None
    return f"{BASE}/{quote(system)}/Named_Boxarts/{quote(filename)}"


def supported(platform_abbr: str | None) -> bool:
    return (platform_abbr or "") in SYSTEMS
