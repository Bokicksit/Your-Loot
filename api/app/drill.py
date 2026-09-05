"""What is inside the furniture.

The room says how much somebody has. This says what it is: click a piece of
furniture and the zone hands over to a layer that can be read rather than
looked at.

Two shapes, because two shapes is what the collections actually are. Pokemon
cards live in binders, so they get the binder: a shelf of spines that opens
into a two-page spread with the real pockets in it, empty ones included —
the gaps are the collection as much as the cards are. Everything else is a
list of things that group naturally by one field — a shelf of systems, of
artists, of series — so it gets a carousel per group.

What may appear is still share.py's answer. Every tile's text is that
module's row() and nothing else: no notes, no tags, no serials, no prices.
The one thing published here that a person typed is the name of a binder,
and that is deliberate — a binder name is a label on a shelf being published
on purpose, the same kind of thing as the display name at the top of the
page, not a private field attached to an item.

The carousels are in the document, as HTML a crawler can read — the same
items the plain profile lists, arranged rather than fetched. Binder pages
are the exception: a Pokedex is 1,025 pockets, so they are asked for when a
binder is opened, from a route as public as the page itself.
"""

import html
import json

from app.imgauth import sign as sign_image
from app.room import tint

# The field each collection groups by, and what a group of them is called.
#
# Declared rather than derived from share.py's sort options, because a sort
# key is not a group: "by year" sorts a shelf of films perfectly and would
# make forty carousels of one film each. This is the field somebody would
# actually use to divide the shelf up.
GROUPS = {
    "games": ("platform_name", "system"),
    "hardware": ("platform_name", "system"),
    "movies": ("format", "format"),
    "books": ("author", "author"),
    "records": ("artist", "artist"),
    "lego": ("theme", "theme"),
    "comics": ("series", "series"),
    "amiibo": ("amiibo_series", "series"),
}

# What shape the frame is, and how the picture sits in it.
#
# A Pokemon card is one shape — every card ever printed is 63 by 88 — so its
# frame is that shape and the art fills it. Nothing else is: a shelf of games
# holds portrait boxes, landscape ones and square cartridges at once, and a
# frame that fills would crop most of them. So everything else gets a fixed
# frame the picture is fitted inside rather than cropped to, which is the
# trade the app's own game shelf already makes, for the same reason: the grid
# stays even and nothing loses its edges.
SHAPE = {"cards": "tall", "records": "square"}
BOX = "box"          # 4:5, the ratio that wastes the least across the lot


def shape(scope):
    return SHAPE.get(scope, BOX)


def _fill(scope):
    return "cover" if scope == "cards" else "contain"


def art(item):
    """The picture, safe to put on a page anybody can open.

    Catalogue art is somebody else's asset host and is a plain link. A
    photograph the owner took is served from /images/, which refuses without
    a session, so it gets a token minted at render time — the same reasoning
    as profile.py's _thumb(), and the same reason a profile should not be
    cached for long.
    """
    url = item.image_url or ""
    if url.startswith("/images/"):
        name = url.rsplit("/", 1)[-1]
        return f"/images/{name}?token={sign_image(name)}"
    return url


def _icon(path):
    return (
        '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        + path + "</svg>"
    )


X = _icon('<path d="M6 6l12 12M18 6L6 18"/>')
LEFT = _icon('<path d="M15 5l-7 7 7 7"/>')
RIGHT = _icon('<path d="M9 5l7 7-7 7"/>')
BACK = _icon('<path d="M15 5l-7 7 7 7"/>')


def shell(scope, title, count, crumb, body):
    """The layer itself: a head that can always get you out, and a body."""
    return (
        '<div class="drill" id="drill-' + scope + '" hidden>'
        '<div class="drill-head">'
        '<button class="icon back" type="button" hidden '
        'aria-label="Back to the shelf">' + BACK + '</button>'
        '<h3>' + html.escape(title) + ' <span>' + html.escape(count) + '</span></h3>'
        '<span class="crumb">' + html.escape(crumb) + '</span>'
        '<span class="spacer"></span>'
        '<button class="icon close" type="button" '
        'aria-label="Back to the room">' + X + '</button>'
        '</div>'
        '<div class="drill-body">' + body + '</div>'
        '</div>'
    )


# --------------------------------------------------------------- carousels


def _row(scope, item):
    from app.share import SPECS

    spec = SPECS.get(scope)
    r = spec["row"](item) if spec else {}
    return (
        str(r.get("title") or ""),
        str(r.get("meta") or ""),
        str(r.get("badge") or ""),
    )


def _group_of(scope, item):
    field = GROUPS.get(scope, (None, None))[0]
    if not field:
        return ""
    return str(getattr(item.attrs, field, "") or "").strip()


def tile(scope, item, j, kind="tile-item"):
    """One thing, as a tile you can click.

    The detail card is built from these attributes rather than from a second
    payload — the tile already carries everything it is allowed to say, so a
    second copy would only be a second thing to keep in step.
    """
    title, meta, badge = _row(scope, item)
    picture = art(item)
    colour = tint(title)
    # The hashed colour is what stands in for a picture, not a frame around
    # one. Fitting a cover inside its box leaves bands at the sides, and with
    # a colour behind it those bands read as a border somebody chose — eight
    # different ones down a shelf. Where there is art, the space around it is
    # the same dark as everything else.
    inner = (
        '<div class="art" style="'
        + ("background-color:var(--bg-2);background-image:url('"
           + html.escape(picture, quote=True) + "')"
           ";background-size:" + _fill(scope)
           + ";background-repeat:no-repeat;background-position:center"
           if picture else "color:" + colour)
        + '"></div>'
        '<div class="t"><strong>' + html.escape(title) + '</strong>'
        + ('<small>' + html.escape(meta) + '</small>' if meta else "")
        + ('<em>' + html.escape(badge) + '</em>' if badge else "")
        + '</div>'
    )
    return (
        '<button type="button" class="' + kind + ' ' + shape(scope) + '" '
        'style="--j:' + str(j) + '" '
        'data-title="' + html.escape(title, quote=True) + '" '
        'data-meta="' + html.escape(meta, quote=True) + '" '
        'data-badge="' + html.escape(badge, quote=True) + '" '
        'data-art="' + html.escape(picture, quote=True) + '" '
        'data-colour="' + colour + '" '
        'data-fill="' + _fill(scope) + '" '
        'data-shape="' + shape(scope) + '">' + inner + '</button>'
    )


def carousels(scope, items):
    """One track per group, biggest first, and the odds and ends last.

    Sorted by size because a shelf reads by its shape: what somebody has most
    of is what they collect, and it should not be four rows down because its
    name starts with W.
    """
    field, noun = GROUPS.get(scope, (None, "group"))
    groups = {}
    for i in items:
        groups.setdefault(_group_of(scope, i) or "", []).append(i)

    # An unnamed group is not a group with an empty name — it is everything
    # this collection does not say that about, and it goes at the end.
    loose = groups.pop("", [])
    order = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    if loose:
        order.append(("Everything else", loose))

    out = []
    for j, (name, rows) in enumerate(order):
        rows = sorted(rows, key=lambda i: (_row(scope, i)[0] or "").lower())
        out.append(
            '<section class="carousel" style="--j:' + str(j) + '">'
            '<div class="head"><strong>' + html.escape(name) + '</strong>'
            '<span>' + str(len(rows)) + '</span>'
            '<div class="rule"></div>'
            '<button type="button" class="more" aria-label="Scroll this row">'
            + RIGHT + '</button></div>'
            '<div class="track">'
            + "".join(tile(scope, i, k) for k, i in enumerate(rows))
            + '</div></section>'
        )
    return '<div class="carousels">' + "".join(out) + '</div>'


# ------------------------------------------------------------- the binders


def spine(binder, filled, j):
    """One binder on the shelf.

    Its colour is the one the owner picked; where they picked none, it is
    hashed from the name so the shelf still reads as a shelf of different
    binders rather than a row of identical black folders.
    """
    colour = binder.color or tint(binder.name, j)
    return (
        '<button type="button" class="binder-spine" data-binder="' + str(binder.id) + '" '
        # what kind of binder this is, so a link straight to somebody's
        # Pokedex can find the right spine without knowing its id or its name
        'data-kind="' + html.escape(binder.kind or "", quote=True) + '" '
        'style="--j:' + str(j) + ';color:' + html.escape(colour, quote=True) + '" '
        'data-name="' + html.escape(binder.name, quote=True) + '">'
        '<span class="name">' + html.escape(binder.name) + '</span>'
        '<span class="n">' + str(filled) + '</span>'
        '</button>'
    )


def shelf(db, user, items, loose_shown=True):
    """The cards layer: a shelf of binders, and a box for everything loose.

    The binders' pages are not in this document. A Pokedex is 1,025 pockets,
    and building that into every profile — for a binder most visitors will
    never open — would make the page heavier than the collection it is
    showing. They are asked for when one is opened.

    The counts on the spines are not. They come from binder_view, the app's
    own answer to what is in a binder, because the cheap version of that
    question is wrong: a set binder's slot is filled by owning the card,
    with or without a row to say so, and counting rows would report a
    complete set as an empty one. It costs one binder read per binder on
    every view of this page, which is the price of the number being true.

    A binder held back is not drawn — but it is still read, because what is
    filed in it decides what counts as loose. Skipping it would tip its cards
    into the box beside it, which is publishing the thing that was hidden.
    """
    from app.binder_view import render as render_binder
    from app.models import Binder

    binders = db.query(Binder).filter(Binder.user_id == user.id).all()
    # position first where it was set, then name — the shelf order somebody
    # arranged, with anything never placed after it rather than in front
    binders.sort(key=lambda b: (b.position is None, b.position or 0, b.name.lower()))

    spines, filed = [], set()
    for j, b in enumerate(binders):
        data = render_binder(db, b, user.id)
        if b.on_profile:
            spines.append(spine(b, data["binder"]["filled"], len(spines)))
        for e in data["entries"]:
            card = e.get("card") or {}
            if card.get("owned_id"):
                filed.add(card["owned_id"])

    # Cards not filed anywhere — loose only if no copy of it is in a binder,
    # since a second Charizard in a box is not the one on the shelf. A
    # collection is not only what is in binders, and a shelf that hid them
    # would be saying something untrue.
    loose = [i for i in items if not any(c.id in filed for c in (i.owned or []))]
    if not loose_shown:
        loose = []

    box = ""
    if loose:
        box = (
            '<button type="button" class="tcgbox" data-loose="1">'
            '<span class="lid"></span><span class="base"></span>'
            '<span class="tag">Loose · ' + str(len(loose)) + '</span></button>'
        )

    note = ""
    if not spines and not box:
        # Two different silences, and saying the wrong one is a small lie:
        # a shelf nobody has filled yet, and a shelf its owner is keeping to
        # themselves.
        note = ('<p class="rail-note">Nothing on show here.</p>'
                if binders or items else
                '<p class="rail-note">Nothing filed yet.</p>')
    elif spines:
        note = ('<p class="rail-note">' + str(len(spines))
                + (" binder" if len(spines) == 1 else " binders")
                + ' on the shelf. Open one.</p>')

    # The line goes above the shelf rather than beside it: alongside the
    # binders it is a column four words wide, and it is a sentence.
    rail = (
        '<div class="shelf">' + note
        + '<div class="binder-rail">' + "".join(spines) + box + '</div>'
        + '</div>'
    )

    loose_grid = (
        '<div class="loose" hidden><div class="loose-grid">'
        + "".join(tile("cards", i, j, kind="loose-card") for j, i in enumerate(loose))
        + '</div></div>'
    )
    return rail + loose_grid


def pages(db, binder, user_id):
    """One binder's pockets, as the page needs them.

    Built from binder_view, which is the app's own answer to what is in a
    binder — including the empty slots, which are the half of a binder that a
    grid of owned cards can never show.
    """
    from app.binder_view import render as render_binder

    data = render_binder(db, binder, user_id)
    slots = []
    for e in data["entries"]:
        card = e.get("card")
        picture = ""
        if card and card.get("image_url"):
            url = card["image_url"]
            if url.startswith("/images/"):
                nm = url.rsplit("/", 1)[-1]
                url = f"/images/{nm}?token={sign_image(nm)}"
            picture = url
        # The fifth field is the line the card would carry anywhere else on
        # this page — the set and its number. Without it a pocket opens onto
        # a species name and a slot number, which is the binder talking
        # rather than the card.
        meta = ""
        if card:
            meta = " · ".join(
                x for x in (
                    card.get("set_name"),
                    f"#{card['card_number']}" if card.get("card_number") else None,
                    card.get("variant"),
                ) if x
            )
        # The sixth field is what a visitor came to find out. binder_view
        # already works it out for the app's own binder — a slot is missing,
        # or holds the card somebody settled on, or holds a stand-in they mean
        # to replace — and it was being dropped on the way out here. It is the
        # difference between a page that shows off a collection and one you
        # can shop from.
        slots.append([
            e.get("label") or "",
            e.get("name") or (card or {}).get("title") or "",
            picture,
            1 if card else 0,
            meta,
            e.get("state") or ("filled" if card else "missing"),
            # the item, so a dead link can fall back to the kept copy
            (card or {}).get("id") or e.get("item_id") or 0,
            # the section this pocket begins, if it begins one
            e.get("section") or "",
        ])
    b = data["binder"]
    return {
        "id": b["id"],
        "name": b["name"],
        # Only the Pokedex gets the tile view: it is the one binder whose
        # empty slots are a list of things that exist and could be bought,
        # because every slot is a species whether or not anybody owns it. A
        # set binder's gaps are the same idea; a custom binder's are just
        # unfilled pockets, and a "missing" filter over them would mean
        # nothing.
        "kind": b.get("kind") or "",
        "cols": b["cols"],
        "rows": b["rows"],
        "double": bool(b["double_page"]),
        "pages": b["pages"],
        "filled": b["filled"],
        "total": b["total"],
        "slots": slots,
    }
