"""A Supporter profile, drawn as a room.

The free profile is a grid, which is an honest way to show a list and a poor
way to show a collection — a shelf is not a spreadsheet, and the thing people
are proud of is the shape of it. So a Supporter gets furniture: cards laid out
on a lamp-lit table, games under a CRT, records on a credenza, LEGO behind
glass.

Every prop is CSS. No photographs, no logos, nothing fetched — which is what
makes it affordable to serve to strangers, and what keeps it working on a page
that must not wait on anything.

Two rules run through the builders below.

The furniture is driven by the collection rather than decorating it. How many
spines stand on the shelf, how many sleeves fill the crate, how many issues
face out of the rack: those are counts, capped at what the furniture holds. A
room with four records looks like four records.

And the colours come from the items themselves, deterministically, so one
person room looks the same every time they open it and different from
everybody else. A hash of the title picks a hue — it is not the card real
colour, which nothing here knows, but it is theirs, and it is stable.
"""

import hashlib
import html

# Hues that sit on the room warm dark ground without fighting the gold.
# Deliberately not a rainbow: a shelf of saturated primaries reads as a toy,
# and the point is a room somebody would actually sit in.
PALETTE = [
    "#c9a94a", "#7fb3d5", "#d98b6a", "#8fd0a8", "#b79ad6",
    "#d6768f", "#6fa8a0", "#c4a882", "#8f9bd0", "#cf9d5c",
]


def tint(seed, offset=0):
    """A colour for one item, stable for the life of that item.

    Hashed rather than random so a room is the same room tomorrow, and drawn
    from a short list rather than the whole spectrum so the shelf still looks
    like it belongs to one person.
    """
    h = hashlib.sha1((seed or "").encode("utf-8")).digest()
    return PALETTE[(h[0] + offset) % len(PALETTE)]


def _title(item):
    return getattr(item, "title", "") or ""


def _props(items, cap, cls, style=""):
    """A run of one prop, one per item, up to what the furniture holds."""
    out = []
    for j, i in enumerate(items[:cap]):
        colour = tint(_title(i), j)
        out.append(
            '<span class="' + cls + '" style="--j:' + str(j)
            + ';color:' + colour + (';' + style if style else '') + '"></span>'
        )
    return "".join(out)


# ---------------------------------------------------------------- the zones
#
# One builder per collection. Each returns the inside of its zone; the wrapper,
# label and stagger index are added once, below, so a zone cannot forget them.


def _cards(items):
    """A low table: an open binder in the middle, boxes and slabs around it,
    a lamp behind throwing a cone up the wall."""
    def page(seq):
        cells = "".join(
            '<i style="color:' + tint(_title(i), j) + '"></i>'
            for j, i in enumerate(seq[:9])
        )
        return cells + '<i style="color:#1a1722"></i>' * max(0, 9 - len(seq[:9]))

    stack = "".join(
        '<i style="color:' + tint(_title(i), 3 + j) + '"></i>'
        for j, i in enumerate(items[:4])
    )
    return (
        '<div class="lamp"><div class="glow"></div><div class="shade"></div>'
        '<div class="stem"></div></div>'
        '<div style="display:flex;align-items:flex-end;gap:1.8cqh;padding:0 3cqh">'
        + _props(items[4:9], 5, "slab prop") +
        '</div>'
        '<div class="plank" style="width:44cqh;height:1cqh;margin-bottom:15cqh">'
        '<span class="lightline"></span><span class="wash"></span></div>'
        '<div class="table-stuff">'
        '<div class="binder-stack">' + stack + '</div>'
        '<div class="binder-open"><div class="page">' + page(items) + '</div>'
        '<div class="page">' + page(items[9:]) + '</div></div>'
        '<span class="cardbox prop" style="color:' + tint("box" + str(len(items))) + '"></span>'
        '</div>'
        '<div class="tabletop"></div><div class="tablelegs"></div>'
    )


def _games(items):
    """A CRT on a media unit, cases along the shelves, a console and pads."""
    rows = ""
    per = 22
    for r in range(2):
        chunk = items[r * per:(r + 1) * per]
        if not chunk:
            break
        rows += '<div class="row">' + _props(chunk, per, "sp") + '</div>'
    return (
        '<div class="crt"><div class="spill"></div><div class="screen"></div>'
        '<div class="knobs"><i></i><i></i></div><span class="led"></span></div>'
        '<div class="mediaunit furn">' + rows + '</div>'
        '<div class="cordrow">'
        '<span class="console16 prop"><span class="cart-in"></span></span>'
        '<span class="pad prop" style="color:#6f6a80"></span>'
        + _props(items[:2], 2, "cart64 prop") +
        '</div>'
    )


def _hardware(items):
    """A steel rack against a pegboard, controllers hanging above it."""
    tiers = ""
    per = 4
    for t in range(2):
        chunk = items[t * per:(t + 1) * per]
        if not chunk:
            break
        tiers += (
            '<div class="tier">'
            + _props(chunk[:2], 2, "tower prop")
            + _props(chunk[2:], 2, "handheld prop")
            + '</div>'
        )
    return (
        '<div class="pegboard"></div>'
        '<div class="hang">' + _props(items[:4], 4, "pad prop") + '</div>'
        '<div class="rack furn">' + (tiers or '<div class="tier"></div>') + '</div>'
    )


def _movies(items):
    """A flatscreen with a soundbar, shelves of slim cases either side."""
    half = max(1, len(items) // 2)
    return (
        '<div class="plank" style="width:52cqh;height:1cqh;margin-bottom:2cqh">'
        '<span class="lightline"></span><span class="wash"></span></div>'
        '<div class="row" style="width:52cqh;height:7cqh;margin-bottom:2cqh">'
        + _props(items[:half], 26, "sp slim bluray") + '</div>'
        '<div class="tv"><div class="spill"></div><div class="screen"></div>'
        '<span class="stand"></span></div>'
        '<div style="height:2cqh"></div>'
        '<span class="soundbar prop"></span>'
        '<div class="row" style="width:56cqh;height:7cqh">'
        + _props(items[half:], 26, "sp slim dvd") + '</div>'
        '<div class="mediaunit furn" style="height:3cqh"></div>'
    )


def _records(items):
    """A credenza: turntable turning on top, a crate of sleeves, a speaker."""
    walls = "".join(
        '<span class="wallsleeve ' + c + '" style="color:' + tint(_title(i), 5 + j) + '"></span>'
        for j, (c, i) in enumerate(zip("abc", items[:3]))
    )
    return (
        walls +
        '<div class="deskrow">'
        '<div class="turntable prop"><span class="platter"></span><span class="arm"></span></div>'
        '<div class="speaker prop"><i></i><i></i></div>'
        '</div>'
        '<div class="credenza"><div class="crate">'
        + _props(items, 26, "sleeve") +
        '</div></div>'
    )


def _books(items):
    """A tall case, four shelves deep, with a plant on the floor beside it."""
    tiers = ""
    per = 16
    for t in range(4):
        chunk = items[t * per:(t + 1) * per]
        tiers += '<div class="tier">' + (_props(chunk, per, "sp") if chunk else "") + '</div>'
    return (
        '<div class="bookcase">' + tiers + '</div>'
        '<span class="pot prop" style="position:absolute;left:-7cqh;bottom:0"></span>'
    )


def _lego(items):
    """A lit glass case: a set on the top shelf, bricks below, figures at the
    bottom. The brick sizes vary with position rather than randomly, so the
    case looks arranged rather than tipped out."""
    tiers = ""
    for t in range(3):
        chunk = items[t * 3:(t + 1) * 3]
        inner = '<span class="lightline"></span>'
        if t == 0 and chunk:
            inner += ('<span class="set-house prop"><span class="roof"></span>'
                      '<span class="walls"></span><span class="door"></span></span>')
            chunk = chunk[1:]
        for j, i in enumerate(chunk):
            inner += (
                '<span class="brick prop" style="--j:' + str(j) + ';color:'
                + tint(_title(i), j) + ';width:' + str(6 + (j % 3) * 2)
                + 'cqh;height:' + str(3 + (j % 2)) + 'cqh"></span>'
            )
        tiers += '<div class="tier">' + inner + '</div>'
    figs = "".join(
        '<span class="minifig prop" style="--j:' + str(j) + ';color:'
        + tint(_title(i), 7 + j) + '"></span>'
        for j, i in enumerate(items[:6])
    )
    return '<div class="vitrine">' + tiers + '<div class="tier">' + figs + '</div></div>'


def _comics(items):
    """A face-out rack on the wall, long boxes below, one issue half pulled."""
    rack = "".join(
        '<span class="issue prop" style="--j:' + str(j) + ';color:'
        + tint(_title(i), j) + '"></span>'
        for j, i in enumerate(items[:4])
    )
    boxes = ('<div class="longbox open"><span class="pulled" style="color:'
             + tint(_title(items[0]) if items else "none", 2) + '"></span></div>')
    boxes += '<div class="longbox"></div>' * min(2, max(0, (len(items) - 1) // 8))
    return (
        '<div class="plank" style="width:36cqh;height:1cqh;margin-bottom:1cqh">'
        '<span class="lightline"></span><span class="wash"></span></div>'
        '<div class="comicrack">' + rack + '</div>'
        '<div style="position:relative">' + boxes + '</div>'
    )


BUILDERS = {
    "cards": _cards,
    "games": _games,
    "hardware": _hardware,
    "movies": _movies,
    "records": _records,
    "books": _books,
    "lego": _lego,
    "comics": _comics,
}


# ------------------------------------------------------------- the heading

# The app's own mark, inlined. A profile is served to somebody who has never
# loaded this application, so there is no sprite sheet on the page to point
# at and no second request worth making for one small shape.
MARK = (
    '<svg class="mark" viewBox="0 0 120 120" width="26" height="26" aria-hidden="true">'
    '<defs><linearGradient id="ylCube" x1="0" y1="0" x2="1" y2="0.7">'
    '<stop offset="0" stop-color="#8b46f0"/><stop offset="0.5" stop-color="#7c4dff"/>'
    '<stop offset="1" stop-color="#3b82f6"/></linearGradient>'
    '<mask id="ylCubeCut" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
    '<rect width="120" height="120" fill="#000"/>'
    '<g stroke-linejoin="round" stroke-linecap="round">'
    '<path d="M60 12 L106 39 L60 66 L14 39 Z" fill="#fff" stroke="#fff" stroke-width="7"/>'
    '<path d="M14 39 L60 66 L60 110 L14 83 Z" fill="#fff" stroke="#fff" stroke-width="7"/>'
    '<path d="M106 39 L60 66 L60 110 L106 83 Z" fill="#fff" stroke="#fff" stroke-width="7"/>'
    '<path d="M14 39 L60 66 L106 39" fill="none" stroke="#000" stroke-width="10"/>'
    '<path d="M60 66 V110" fill="none" stroke="#000" stroke-width="10"/>'
    '<rect x="45" y="39" width="30" height="35" rx="8" fill="#000" stroke="#000" stroke-width="10"/>'
    '<path d="M55 48 V66 H68" fill="none" stroke="#fff" stroke-width="7"/>'
    '</g></mask></defs>'
    '<rect width="120" height="120" fill="url(#ylCube)" mask="url(#ylCubeCut)"/>'
    '</svg>'
)


def heading(who, sub):
    """The same title bar the app wears, on the page other people see.

    A profile is this collection seen from outside, and it should look like
    the thing it is part of — the mark, and whose loot it is. Not the app's
    header wholesale: no globe back to a profile you are already reading,
    and no build number, which is a fact about the server and means nothing
    to a visitor.
    """
    return (
        '<div class="pub-brand">'
        '<h1>' + MARK + '<span>' + html.escape(who) + '\u2019s <em>Loot</em></span></h1>'
        '<span class="sub">' + html.escape(sub) + '</span>'
        '</div>'
    )


# ------------------------------------------------------------------ the room


def _motes(n=16):
    """Dust in the lamplight. Positions are fixed rather than random so the
    page is byte-identical between requests and can be cached."""
    out = []
    for k in range(n):
        left = (k * 61) % 97
        delay = (k * 7) % 18
        dur = 12 + (k % 7) * 2
        out.append(
            '<span style="left:' + str(left) + '%;bottom:' + str((k * 13) % 40)
            + '%;animation-duration:' + str(dur) + 's;animation-delay:-'
            + str(delay) + 's"></span>'
        )
    return '<div class="motes2">' + "".join(out) + '</div>'


def render(who, shelves, labels, stamp, total, name="", drills=""):
    """The whole room: one zone per published shelf, in the order they were
    published.

    `shelves` is [(scope, items)]. A shelf with nothing in it is not drawn —
    an empty piece of furniture says something untrue about the person.

    `drills` is what is inside the furniture, from drill.py, and it is the
    reason a zone is a button: clicking one is how you get from how much
    somebody has to what it actually is.
    """
    zones = []
    i = 0
    for scope, items in shelves:
        build = BUILDERS.get(scope)
        if build is None or not items:
            continue
        label = html.escape(labels.get(scope, scope))
        zones.append(
            '<div class="zone z-' + scope + '" style="--i:' + str(i) + '" '
            'data-scope="' + scope + '" role="button" tabindex="0" '
            'aria-label="Open ' + label.lower() + '">'
            + build(items)
            + '<span class="z-label">' + label + ' <b>' + str(len(items)) + '</b></span>'
            + '</div>'
        )
        i += 1

    if not zones:
        return ""

    return (
        '<div class="room2-wrap">'
        + heading(who, str(total) + ' things · ' + stamp) +
        '<div class="room2" data-u="' + html.escape(name, quote=True) + '">'
        '<div class="floor"></div><div class="rug"></div><div class="skirt"></div>'
        '<div class="scene"><div class="scene-strip">' + "".join(zones) + '</div></div>'
        + _motes() +
        '<div class="vignette"></div>'
        '<div class="panhint">drag to look around</div>'
        + drills +
        '</div>'
        '<div class="room-foot">Kept with <a href="/">Your Loot</a></div>'
        '</div>'
    )
