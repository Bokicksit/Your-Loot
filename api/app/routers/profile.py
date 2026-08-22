"""A profile somebody can send a stranger.

Two halves that barely touch. `/api/profile` is the owner deciding: what they
are called and which shelves they are willing to show. `/u/<name>` is the
result, served to anybody, and it is the only page in this application that
answers without a session.

Rendered here as HTML rather than by the app's React, and that is the whole
reason this file exists. A profile is for pasting into a chat and for being
found — and link previews in Discord, iMessage, Slack and every other unfurler
read `og:` tags out of the first response without running any JavaScript. A
single-page app hands them an empty shell. So this returns a real document,
with real tags, on the first byte.

What may appear is not decided here. `app/share.py` already answers that for
the downloadable file: a row built from a named list of fields, with nothing
that came out of a free-text box — no notes, no tags, no serial or certificate
numbers, no prices. That list is the reason this feature is publishable at all,
and it is reused rather than rewritten, because a second answer to "what is
safe to show" would be a second thing to get wrong.

Nothing is public until it is switched on. A profile with no shelves chosen is
a 404, not an empty page: somebody who has not opted in does not have a URL.
"""

import html
import random
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import screennames
from app.auth import OWNER_ID, current_user, multi_user
from app.config import settings
from app.db import get_db
from app.models import Setting, User
from app.modules import available
from app.plans import themed
from app.imgauth import sign as sign_image
from app import drill as drill_view
from app import room as room_view
from app.share import TITLES

router = APIRouter()

# Which shelves this person shows, as a comma-separated list in the same
# key/value table `owner_name` lives in — it is a preference about
# presentation, which is what that table is for.
PUBLIC_KEY = "public_collections"
# Whether the box of cards that are not in any binder is on the shelf too.
# On unless it is turned off: publishing the cards shelf publishes the cards,
# and a collection is not only what is in binders. Some of it is a box.
LOOSE_KEY = "public_loose"


def shown_scopes(raw: str | None) -> list[str]:
    """Which shelves a stored setting actually publishes.

    Intersected with what this install carries, so a shelf switched off at
    the service level cannot be published by a setting that outlived it.

    Split out from the lookup because the admin panel asks the same question
    about everybody at once, and two answers to "is this profile published"
    is exactly how the panel came to link pages that do not exist.
    """
    here = set(available())
    return [s for s in (x.strip() for x in (raw or "").split(",")) if s and s in here]


def _shown(db: Session, user_id: int) -> list[str]:
    row = db.get(Setting, (user_id, PUBLIC_KEY))
    return shown_scopes(row.value if row else "")


def _loose_shown(db: Session, user_id: int) -> bool:
    row = db.get(Setting, (user_id, LOOSE_KEY))
    return (row.value if row else "1") != "0"


def _display_name(db: Session, user_id: int) -> str:
    row = db.get(Setting, (user_id, "owner_name"))
    return (row.value if row else None) or ""


# ---------------------------------------------------------------- the owner


class ProfileIn(BaseModel):
    # Absent means "leave it alone"; the two halves are set independently
    # because renaming yourself and publishing a shelf are different decisions.
    # Generous on purpose. The rules live in one place — screennames.check() —
    # so that every refusal comes back as a sentence somebody can act on
    # rather than as a schema error. This bound is only here to throw away an
    # absurd payload before it is worth thinking about.
    screen_name: str | None = Field(default=None, max_length=100)
    collections: list[str] | None = None
    loose: bool | None = None


def _must_be_on() -> None:
    """404 rather than 403 where profiles are off.

    An install that does not offer them has no such endpoint, which is a
    different statement from "you may not" — and it keeps the settings screen
    from having to explain a feature this server does not have.
    """
    if not settings.public_profiles:
        raise HTTPException(404, "Not found")


@router.get("/api/profile")
def my_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """What I am called, and which shelves I show."""
    _must_be_on()
    if not multi_user():
        # A home server: one person, no accounts, so no name to claim. The
        # page lives at a fixed address instead, and the client draws the
        # publish switches without the name form.
        return {
            "screen_name": None,
            "url": "/loot",
            "fixed_url": True,
            "can_claim": False,
            "name_revoked": False,
            "collections": _shown(db, user.id),
            "loose": _loose_shown(db, user.id),
            "available": [
                {"scope": s, "label": TITLES.get(s, s)} for s in available()
            ],
            "themed": themed(user),
            "links": focus_links(db, user, "/loot"),
        }
    now = screennames.current_for(db, user.id)
    return {
        "screen_name": now.display if now else None,
        "url": f"/u/{now.name}" if now else None,
        # A name is claimed once and never changed, so the form has to know
        # whether it is a form at all or just a label.
        "can_claim": now is None,
        # And if theirs was taken away, why their profile went dark — somebody
        # not told simply finds a broken URL and cannot act on it.
        "name_revoked": screennames.was_revoked(db, user.id),
        "collections": _shown(db, user.id),
        "loose": _loose_shown(db, user.id),
        "available": [{"scope": s, "label": TITLES.get(s, s)} for s in available()],
        "themed": themed(user),
        # One address per shelf, for pointing somebody at the collection they
        # care about instead of at everything. Empty where there is no room to
        # open into — see focus_links.
        "links": focus_links(db, user, f"/u/{now.name}") if now else [],
    }


@router.put("/api/profile")
def set_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    _must_be_on()
    if body.screen_name is not None:
        if not multi_user():
            raise HTTPException(409, "A home server's page lives at /loot — there is no name to claim.")
        try:
            # an administrator may go to two characters; nobody else may
            screennames.claim(
                db, user.id, body.screen_name,
                floor=screennames.floor_for(user),
            )
        except screennames.NameProblem as e:
            raise HTTPException(409, str(e))

    if body.loose is not None:
        row = db.get(Setting, (user.id, LOOSE_KEY))
        if row is None:
            row = Setting(user_id=user.id, key=LOOSE_KEY)
            db.add(row)
        row.value = "1" if body.loose else "0"

    if body.collections is not None:
        here = set(available())
        keep = [s for s in body.collections if s in here]
        row = db.get(Setting, (user.id, PUBLIC_KEY))
        if row is None:
            row = Setting(user_id=user.id, key=PUBLIC_KEY)
            db.add(row)
        row.value = ",".join(keep)

    db.commit()
    return my_profile(db=db, user=user)


# --------------------------------------------------------------- the public


# Read once at import. The page has no application stylesheet to inherit
# from — a stranger arriving from a link has never loaded this app — so the
# rules travel with it.
_HERE = Path(__file__).resolve().parents[1]
_CSS = (_HERE / "profile_theme.css").read_text(encoding="utf-8")
# Only sent to a Supporter's page. It is 30 KB of furniture and there is no
# reason to make everybody else download a room they do not have.
_ROOM_CSS = (_HERE / "profile_room.css").read_text(encoding="utf-8")
_ROOM_CSS += (_HERE / "profile_drill.css").read_text(encoding="utf-8")
_JS = (_HERE / "profile.js").read_text(encoding="utf-8")
_DRILL_JS = (_HERE / "profile_drill.js").read_text(encoding="utf-8")

# The icons the jump rail uses, one per collection, from the design's sprite.
_GLYPHS = {
    "amiibo": '<circle cx="12" cy="6.5" r="2.6"/><path d="M8.5 20v-4a3.5 3.5 0 017 0v4M6 20h12"/>',
    "cards": '<rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M9 7.5h6M9 11h4"/>',
    "games": '<rect x="2.5" y="7" width="19" height="11" rx="4.5"/><path d="M8 10.8v3.4M6.3 12.5h3.4"/><circle cx="15.8" cy="11.6" r="1.15"/><circle cx="18.4" cy="14.2" r="1.15"/>',
    "hardware": '<rect x="3" y="6" width="18" height="12" rx="2.5"/><path d="M6.5 9.5h4M8.5 7.5v4"/><circle cx="16.5" cy="10.5" r="1.2"/><path d="M6 21h12"/>',
    "movies": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 9.5h18M3 14.5h18M8 5v14M16 5v14"/>',
    "books": '<path d="M5 4.5h9.5a3 3 0 013 3V20H8a3 3 0 01-3-3z"/><path d="M5 17.2a3 3 0 013-3h9.5"/><path d="M9.5 4.5V14"/>',
    "records": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.4"/>',
    "lego": '<rect x="4" y="8.5" width="16" height="10" rx="1.8"/><path d="M8.5 8.5V6.6a1.6 1.6 0 013.2 0v1.9M13.2 8.5V6.6a1.6 1.6 0 013.2 0v1.9"/>',
    "comics": '<rect x="4" y="4.5" width="16" height="15" rx="2.2"/><path d="M8 9h5M8 12.5h8M8 16h4"/>',
}

# What frame each shelf's pictures get. drill.py answers the same question
# for the room, and it is the same answer — asked here through the same
# function so the two pages cannot drift apart.


def _icon(scope: str) -> str:
    inner = _GLYPHS.get(scope)
    if not inner:
        return ""
    return (
        '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{inner}</svg>'
    )


def _page(title: str, description: str, body: str, url: str, room: bool = False) -> str:
    """A document, not an app shell.

    The og: tags are the point of rendering server-side, so they are not
    optional decoration — they are what makes a pasted link show anything at
    all in a chat window.
    """
    t, d = html.escape(title), html.escape(description)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<meta property="og:type" content="profile">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{html.escape(url)}">
<link rel="canonical" href="{html.escape(url)}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="/assets/favicon.svg">
<style>{_CSS}{_ROOM_CSS if room else ''}</style>
</head><body class="{"room2-page" if room else "pub"}">{body}
<script>{_JS}{_DRILL_JS if room else ''}</script>
</body></html>"""


@router.get("/u/{name}", response_class=HTMLResponse)
def public_profile(
    name: str, request: Request, db: Session = Depends(get_db)
):
    """Somebody's shelves, to anybody, with no session.

    Names are claimed once and never changed, so there is no redirect to make
    — a URL either belongs to somebody or it does not. A revoked name is gone
    rather than forwarded: forwarding it would be pointing at the person whose
    name was taken away.
    """
    _must_be_on()
    row = screennames.holder(db, name)
    if row is None or row.revoked:
        raise HTTPException(404, "No such profile")
    owner = db.get(User, row.user_id)
    if owner is None:
        raise HTTPException(404, "No such profile")
    who = _display_name(db, row.user_id) or row.display
    return _render_profile(db, owner, who, f"/u/{row.name}", parked=True)


@router.get("/loot", response_class=HTMLResponse)
def solo_profile(db: Session = Depends(get_db)):
    """The owner's shelves, at an address that needs no name.

    A home server has one collection and one person, so a claimed screen name
    would be a formality — this is the same page /u/<name> serves, at a fixed
    path instead. Only on single-user installs: where there are accounts, a
    URL that means "the owner" would be a page about whoever runs the server
    that they never asked for.

    The fixed path is also the point of it operationally. Everything the page
    needs lives under this one prefix (the binder data included) plus the
    token-guarded /images/, so a tunnel can expose exactly this and nothing
    else — see the user guide. Publishing is still the same opt-in: nothing
    ticked in settings, no page.
    """
    _must_be_on()
    if multi_user():
        raise HTTPException(404, "Not found")
    owner = db.get(User, OWNER_ID)
    if owner is None:
        raise HTTPException(404, "Not found")
    who = _display_name(db, OWNER_ID) or "Your"
    return _render_profile(db, owner, who, "/loot")


# The two shelves inside cards that are worth their own address. Both resolve
# to the cards layer; what differs is which thing is open when you arrive and
# what the link says about itself when it is pasted somewhere.
FOCUS_ALIASES = {"pokedex": "cards", "binders": "cards"}
FOCUS_TITLES = {"pokedex": "Pokédex", "binders": "Binders"}


def focus_label(focus: str) -> str:
    """What a focused link calls itself, in a share preview and a heading."""
    return FOCUS_TITLES.get(focus) or TITLES.get(focus, focus)


def _render_profile(
    db: Session, owner: User, who: str, base: str, parked: bool = False,
    focus: str = "",
):
    """The page itself, for whoever `base` points at.

    `base` is the one address this profile answers on — /u/<name>, or /loot on
    a home server — and everything the page fetches later hangs off it, so
    the page and its data always travel together through whatever is in
    front of the server.

    `parked` says what an empty one does. A screen name is taken at sign-up,
    so its address exists before anybody has chosen what to show, and a link
    given out early should read as "not yet" rather than as a broken URL. A
    home server's address is not handed out by anything — nobody has it until
    its owner sends it — so there is nothing to park, and it stays absent
    until there is something to see.
    """
    scopes = _shown(db, owner.id)
    if not scopes and not parked:
        raise HTTPException(404, "No such profile")
    if not scopes:
        # A name claimed, nothing chosen to show yet. The address is real —
        # it was taken at sign-up and belongs to this person — so it answers
        # with a page that has their name on it and nothing else: no counts,
        # no shelves, no hint of what they keep. Publishing is still the same
        # decision it was; this only stops the link somebody was given from
        # reading as a mistake before they have made it.
        return HTMLResponse(
            _page(
                title=f"{who} · Your Loot",
                description=f"{who} keeps a collection on Your Loot.",
                body=(
                    '<div class="pub-wrap">'
                    + room_view.heading(who, "Not published yet")
                    + '<section class="pub-sec pub-empty"><p>'
                    + html.escape(random.choice(TAGLINES))
                    + "</p></section>"
                    + '<div class="pub-foot">Show off <a href="/">Your Loot</a></div>'
                    + "</div>"
                ),
                url=f"{(settings.public_url or '').rstrip('/')}{base}",
            )
        )

    from app.routers.share import everything  # circular at module scope
    shelves = [(scope, everything(scope, db, owner)) for scope in scopes]
    total = sum(len(items) for _s, items in shelves)
    biggest = max(shelves, key=lambda x: len(x[1]))[0] if shelves else None
    stamp = f"{date.today():%B %Y}"

    # the four numbers somebody actually wants at a glance
    stats = "".join(
        f'<div class="stat"><span class="k">{k}</span><span class="v">{v}</span></div>'
        for k, v in [
            ("Things", str(total)),
            ("Categories", f"{len(scopes)} <small>of {len(available())}</small>"),
            (
                "Largest",
                f"{html.escape(TITLES.get(biggest, biggest or ''))} "
                f"<small>{len(dict(shelves).get(biggest, []))}</small>"
                if biggest else "—",
            ),
            ("Updated", f"{date.today():%b} <small>{date.today():%Y}</small>"),
        ]
    )

    jump = "".join(
        f'<a href="#s-{s}">{_icon(s)}{html.escape(TITLES.get(s, s))} '
        f"<b>{len(items)}</b></a>"
        for s, items in shelves
    )

    if total == 0:
        # A published page with nothing on it yet. A grid of zero items and a
        # jump rail to empty sections would present absence as a layout bug;
        # one line says it on purpose.
        sections = (
            '<section class="pub-sec pub-empty"><p>'
            + html.escape(random.choice(TAGLINES))
            + "</p></section>"
        )
    else:
        sections = "".join(
            f'<section class="pub-sec" id="s-{s}">'
            f"<h2>{html.escape(TITLES.get(s, s))} <span>{len(items)}</span></h2>"
            f'<div class="pub-grid">'
            + "".join(_row_html(s, i) for i in items)
            + "</div></section>"
            for s, items in shelves
        )

    # The room: the same shelves, drawn as furniture rather than as a grid.
    # Who gets it is plans.themed() — a Supporter where the service sells
    # something, everybody where it does not. It falls back on its own —
    # render() returns nothing if no published shelf has a builder — so a
    # room is never an empty stage.
    room = ""
    if themed(owner):
        labels = {s: TITLES.get(s, s) for s in scopes}
        drills = "".join(
            drill_view.shell(
                scope,
                labels.get(scope, scope),
                str(len(items)),
                _crumb(scope, items),
                drill_view.shelf(db, owner, items, _loose_shown(db, owner.id))
                if scope == "cards"
                else drill_view.carousels(scope, items),
            )
            for scope, items in shelves
            if items
        )
        room = room_view.render(
            who, shelves, labels, stamp, total, base=base, drills=drills,
            focus=focus,
        )

    body = (
        '<div class="pub-wrap">'
        + room_view.heading(who, f"{total} things · {stamp}")
        + f'<div class="stats">{stats}</div>'
        + (f'<div class="jump">{jump}</div>' if total else "")
        + sections
        + '<div class="pub-foot">Show off <a href="/">Your Loot</a></div>'
        + "</div>"
    )

    # A focused link is a link to one shelf, so it says that where it is
    # pasted: the preview names the collection and counts that shelf, not the
    # whole room. Everything else about the page is identical — same document,
    # same room, one layer already open.
    if focus:
        label = focus_label(focus)
        shown = dict(shelves).get(FOCUS_ALIASES.get(focus, focus), [])
        head = f"{who} · {label} · Your Loot"
        blurb = f"{who} keeps {len(shown)} in {label.lower()} on Your Loot."
    else:
        head = f"{who} · Your Loot"
        blurb = (
            f"{who} keeps {total} things in "
            + ", ".join(TITLES.get(s, s).lower() for s in scopes)
            + "."
        )

    return HTMLResponse(
        _page(
            title=head,
            description=blurb,
            body=room or body,
            # PUBLIC_URL, not the request. Behind nginx the request says
            # whatever the internal hop was called — "http://localhost" —
            # and og:url and canonical are the two places that must be the
            # address people actually type.
            #
            # The focus rides on this one and not on `base`: canonical should
            # name the address that was actually asked for, while the room
            # keeps fetching its binders from the profile root.
            url=f"{(settings.public_url or '').rstrip('/')}{base}"
                + (f"/{focus}" if focus else ""),
            room=bool(room),
        )
    )


@router.get("/u/{name}/{focus}", response_class=HTMLResponse)
def public_profile_focused(
    name: str, focus: str, request: Request, db: Session = Depends(get_db)
):
    """One shelf of somebody's profile, at its own address.

    /u/bo/games, /u/bo/records, /u/bo/pokedex. The same page /u/bo serves —
    same document, same room — arriving with that shelf already open, so a
    link can be about one collection instead of about everything somebody
    keeps. Most people sign up for one collection; this is how they hand
    somebody that one.

    Supporter-only, and not as a paywall bolted on: the room is what these
    open *into*, and the room is what a Supporter gets. A free profile is a
    grid with nothing to drill, so a focused link to one would be a link to a
    layer that does not exist there. It answers 404 rather than falling back
    to the whole page, because a link that quietly shows something else is
    worse than one that admits it is not there.

    Every gate the plain profile passes, this passes first, in the same order
    — and then two of its own: the shelf has to be one this person publishes,
    and a binder link has to have a binder behind it.
    """
    _must_be_on()
    row = screennames.holder(db, name)
    if row is None or row.revoked:
        raise HTTPException(404, "No such profile")
    owner = db.get(User, row.user_id)
    if owner is None:
        raise HTTPException(404, "No such profile")

    scope = FOCUS_ALIASES.get(focus, focus)
    if scope not in _shown(db, row.user_id):
        raise HTTPException(404, "No such profile")
    # The room is the thing being linked into.
    if not themed(owner):
        raise HTTPException(404, "No such profile")
    if focus in FOCUS_ALIASES and not _published_binders(db, owner, focus):
        raise HTTPException(404, "No such profile")

    who = _display_name(db, row.user_id) or row.display
    return _render_profile(db, owner, who, f"/u/{row.name}", focus=focus)


def _published_binders(db: Session, owner: User, focus: str) -> bool:
    """Is there anything behind a binder link?

    A Pokedex link wants the dex specifically; a binders link wants any shelf
    at all. Both ask about `on_profile`, because a binder held back is absent
    rather than merely undrawn — the same rule the binder route itself
    applies, asked earlier so the address never opens onto nothing.
    """
    from app.models import Binder

    q = db.query(Binder).filter(
        Binder.user_id == owner.id, Binder.on_profile.is_(True)
    )
    if focus == "pokedex":
        q = q.filter(Binder.kind == "dex")
    return db.query(q.exists()).scalar()


@router.get("/loot/{focus}", response_class=HTMLResponse)
def solo_profile_focused(focus: str, db: Session = Depends(get_db)):
    """The same one-shelf address on a home server, where the page is /loot.

    Kept in step with the /u/ version deliberately rather than left to the
    hosted service: on an install that sells nothing, themed() is true for
    the one person there, so the gate below is the same gate and reads the
    same way — it simply never refuses anybody.
    """
    _must_be_on()
    if multi_user():
        raise HTTPException(404, "Not found")
    owner = db.get(User, OWNER_ID)
    if owner is None:
        raise HTTPException(404, "Not found")
    scope = FOCUS_ALIASES.get(focus, focus)
    if scope not in _shown(db, OWNER_ID) or not themed(owner):
        raise HTTPException(404, "Not found")
    if focus in FOCUS_ALIASES and not _published_binders(db, owner, focus):
        raise HTTPException(404, "Not found")
    who = _display_name(db, OWNER_ID) or "Your"
    return _render_profile(db, owner, who, "/loot", focus=focus)


def focus_links(db: Session, owner: User, base: str) -> list[dict]:
    """Every one-shelf address this profile actually answers on.

    Built here rather than assembled in the browser so that the settings
    screen can only ever offer a link that works: the binder ones depend on
    what is published inside cards, which is a question this side of the
    wire. A profile with no room gets none of them, for the same reason the
    routes refuse — there is no layer to open.
    """
    if not themed(owner):
        return []
    out = []
    for scope in _shown(db, owner.id):
        out.append({"path": f"{base}/{scope}", "label": TITLES.get(scope, scope)})
        if scope == "cards":
            for extra in ("pokedex", "binders"):
                if _published_binders(db, owner, extra):
                    out.append(
                        {"path": f"{base}/{extra}", "label": FOCUS_TITLES[extra]}
                    )
    return out


@router.get("/loot/binder/{binder_id}")
def solo_binder(binder_id: int, db: Session = Depends(get_db)):
    """The pockets of a binder on the /loot page — same gates, solo address.

    Under /loot on purpose: the page and its data share one prefix, which is
    what lets a tunnel expose the room without exposing the server.
    """
    _must_be_on()
    if multi_user():
        raise HTTPException(404, "Not found")
    owner = db.get(User, OWNER_ID)
    if owner is None or "cards" not in _shown(db, OWNER_ID) or not themed(owner):
        raise HTTPException(404, "No such profile")
    return _binder_payload(db, owner, binder_id)


@router.get("/u/{name}/binder/{binder_id}")
def public_binder(name: str, binder_id: int, db: Session = Depends(get_db)):
    """One binder's pockets, for the profile that is already public.

    Every gate the page passes, this passes again, in the same order and from
    the same functions — profiles on, a name that is held, cards published,
    and a room to draw them in. A page and the thing it fetches disagreeing
    about who may look is how a feature like this leaks, so neither is
    trusted to have already asked.

    Empty slots are in the answer on purpose. A binder is as much what is
    missing as what is there, and a list of only the cards somebody owns is a
    different object — that one is already on the page as the grid.
    """
    _must_be_on()
    row = screennames.holder(db, name)
    if row is None or row.revoked:
        raise HTTPException(404, "No such profile")
    if "cards" not in _shown(db, row.user_id):
        raise HTTPException(404, "No such profile")

    owner = db.get(User, row.user_id)
    if owner is None or not themed(owner):
        raise HTTPException(404, "No such profile")

    return _binder_payload(db, owner, binder_id)


def _binder_payload(db: Session, owner: User, binder_id: int):
    from app.models import Binder

    binder = db.get(Binder, binder_id)
    if binder is None or binder.user_id != owner.id or not binder.on_profile:
        # A binder held back is absent, not merely undrawn. A page that does
        # not show it and a route that hands it over on request are not the
        # same feature, and the second one is the one that counts.
        raise HTTPException(404, "No such binder")
    return drill_view.pages(db, binder, owner.id)


# What an empty profile says instead of a grid of nothing. One is drawn at
# random on every view — no per-person assignment, nothing stored — so the
# page stays alive without anybody having chosen anything. Bo approved the
# list; the register is the app's own: dry, no exclamation marks.
TAGLINES = [
    "Nothing on the shelves yet.",
    "Nothing here yet.",
    "The shelves are up. Nothing on them yet.",
    "Empty shelves, for now.",
    "Nothing catalogued yet.",
    "Not a thing on it yet.",
    "This page is waiting on its collection.",
    "This one's still in boxes.",
    "Shelves built. Collection pending.",
    "Blank shelves and good intentions.",
    "Still at the shelf-building stage.",
    "The room is furnished. The shelves are not.",
    "Nothing on show — nothing hidden either.",
    "Come back when the boxes are unpacked.",
    "All the shelf, none of the stuff.",
    "Furniture first, collection second.",
    "Every collection starts here.",
    "Nothing yet — which is what a start looks like.",
    "An empty shelf is still a shelf.",
    "First card, first game, first anything — still to come.",
    "Give it a week.",
    "The collecting is happening. The cataloguing hasn't caught up.",
    "Ask them again in a month.",
    "Somebody is about to start.",
    "Early days.",
]


def _crumb(scope: str, items) -> str:
    """The line under the heading: what this shelf is divided by.

    Cards say binders because that is what they are kept in; everything else
    says the field its carousels are grouped by, so the drill announces how
    it is arranged rather than making somebody work it out.
    """
    if scope == "cards":
        return "Binders and loose cards"
    noun = drill_view.GROUPS.get(scope, (None, None))[1]
    if not noun:
        return ""
    seen = {drill_view._group_of(scope, i) for i in items}
    seen.discard("")
    # "series" is its own plural — "2 seriess" is what blind pluralising did
    plural = noun if noun.endswith("s") else noun + "s"
    return f"{len(seen)} {noun if len(seen) == 1 else plural}"


def _thumb(item) -> str:
    """The picture, for a page anybody can open.

    Two kinds of URL end up on an item and they are not equally public.
    Catalogue art is somebody else's asset host and needs nothing — it is a
    plain link. A photograph the owner took is served by this application from
    /images/, which refuses without a session, so on a public page it would
    render as a broken frame.

    So local ones get a signed token, minted fresh on every render. That is
    the reason it is done here rather than stored: the token is short-lived by
    design, and a page held in a cache longer than the token lives would show
    exactly the broken frames this avoids. Worth remembering if edge caching
    is ever put in front of profiles — the tokens are what makes it unsafe to
    cache for long.

    Publishing a shelf is publishing its pictures. That is what the tick box
    said it would do.
    """
    url = item.image_url or ""
    if not url:
        return '<div class="placeholder"></div>'
    if url.startswith("/images/"):
        name = url.rsplit("/", 1)[-1]
        url = f"/images/{name}?token={sign_image(name)}"
    return (
        f'<img class="art" src="{html.escape(url)}" alt="" '
        'loading="lazy" decoding="async">'
    )


def _row_html(scope: str, item) -> str:
    """One card in the grid, built from share.py's row for this collection.

    Reused rather than rewritten: that function is the answer to what is safe
    to publish — name, the line of metadata, and the condition badge, with
    nothing that came out of a free-text box — and it has already been thought
    about once.
    """
    from app.share import SPECS

    spec = SPECS.get(scope)
    if spec is None:
        return ""
    r = spec["row"](item)
    name = html.escape(str(r.get("title") or ""))
    meta = html.escape(str(r.get("meta") or ""))
    badge = html.escape(str(r.get("badge") or ""))
    frame = " " + drill_view.shape(scope)
    return (
        f'<article class="pub-item{frame}">{_thumb(item)}<div class="txt">'
        f"<strong>{name}</strong>"
        + (f"<small>{meta}</small>" if meta else "")
        + (f'<span class="cond">{badge}</span>' if badge else "")
        + "</div></article>"
    )
