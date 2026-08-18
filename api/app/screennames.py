"""Choosing a screen name, and what may not be one.

Profiles live under /u/, which was a deliberate choice: at the root, every
name somebody claims is a page this app can never have, and the list of pages
it wants grows for as long as it is worked on. Two characters buy that problem
away entirely.

So the reserved list here is short, and about the shape of a name rather than
about protecting routes.

What it is not is a promise that nothing offensive gets through. A word list
catches the obvious and nothing more: substitutions, spacing and combinations
all defeat it, and it refuses innocent names by accident — Scunthorpe is the
example everybody uses because it keeps happening. So this is a filter, the
admin panel is the backstop, and the terms should say the latter rather than
implying the former.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScreenName

# Letters, digits and single separators, starting and ending on something
# alphanumeric. No leading or trailing punctuation and no runs of it — "b..o"
# and "bo-" are the shapes used to be mistaken for "bo". Length is checked
# separately, in numbers, because two callers want different floors and a
# bound baked into a regex cannot be one of them.
SHAPE = re.compile(r"^[a-z0-9](?:[a-z0-9]|[._-](?=[a-z0-9]))*[a-z0-9]$")

# Three for everybody, two for an administrator.
#
# Not a perk. A two-character name is scarce, and the operator of a service is
# the one person who can hold one without it looking like a land grab — they
# are also the only account that already exists before anybody else can claim
# anything. Everyone else starts at three, which keeps roughly thirteen
# hundred short names out of circulation rather than gone.
MIN_NAME = 3
MIN_NAME_ADMIN = 2
MAX_NAME = 30

# Words that would read as the app speaking rather than a person, plus the few
# paths that exist under /u/ itself. Short on purpose: the prefix means this
# does not have to guess at every page the site might grow.
RESERVED = {
    "admin", "administrator", "api", "app", "assets", "auth", "billing",
    "help", "images", "login", "logout", "me", "moderator", "mod", "official",
    "privacy", "root", "settings", "signin", "signup", "staff", "support",
    "system", "terms", "u", "user", "users", "yourloot", "loot",
}

# Deliberately small and deliberately unclever. Everything here is a whole
# word somebody would have to type on purpose; nothing here tries to catch a
# spelling somebody invented to get past it, because that is a game this
# cannot win and the admin panel can.
BLOCKED = {
    "cunt", "fag", "faggot", "nigger", "nigga", "paki", "rape", "rapist",
    "retard", "tranny", "kike", "spic", "whore", "pedo", "paedo", "nonce",
}


class NameProblem(Exception):
    """Why a name was refused, in words a person can act on."""


def fold(name: str) -> str:
    return (name or "").strip().lower()


def floor_for(user) -> int:
    """How short this account may go. Two for an administrator."""
    return MIN_NAME_ADMIN if getattr(user, "is_admin", False) else MIN_NAME


WORDS = {2: "Two", 3: "Three"}


def check(name: str, *, floor: int = MIN_NAME) -> str:
    """The folded name, or a NameProblem saying what is wrong with it."""
    folded = fold(name)
    if not folded:
        raise NameProblem("Pick a name.")
    if len(folded) < floor:
        raise NameProblem(f"{WORDS.get(floor, floor)} characters or more.")
    if len(folded) > MAX_NAME:
        raise NameProblem(f"{MAX_NAME} characters at most.")
    if not SHAPE.match(folded):
        raise NameProblem(
            "Letters, numbers, and single dots, dashes or underscores between "
            "them — starting and ending with a letter or number."
        )
    if folded in RESERVED:
        raise NameProblem("That one is reserved. Try another.")
    # whole words only: "assassin" contains none of these, and a check that
    # thought it did would be the more common failure
    parts = set(re.split(r"[._-]+", folded))
    if parts & BLOCKED or folded in BLOCKED:
        raise NameProblem("Pick something else.")
    return folded


def holder(db: Session, name: str) -> ScreenName | None:
    """The row for this name, revoked or not — a revoked one still counts,
    because the point of keeping it is that nobody gets it again."""
    return db.scalar(select(ScreenName).where(ScreenName.name == fold(name)))


def current_for(db: Session, user_id: int) -> ScreenName | None:
    """The name this account holds now, if it still holds one."""
    return db.scalar(
        select(ScreenName).where(
            ScreenName.user_id == user_id, ScreenName.revoked.is_(False)
        )
    )


def was_revoked(db: Session, user_id: int) -> bool:
    """Has a name of theirs been taken away?

    Asked so the settings page can say why their profile went dark. Somebody
    who is not told simply finds their URL broken and has no idea what to do
    about it.
    """
    return (
        db.scalar(
            select(ScreenName.id).where(
                ScreenName.user_id == user_id, ScreenName.revoked.is_(True)
            ).limit(1)
        )
        is not None
    )


def claim(db: Session, user_id: int, wanted: str, *, floor: int = MIN_NAME) -> ScreenName:
    """Take a name. Once.

    Refused outright if this account already holds one — not because it is
    hard to implement, but because a name that can move is a URL that can
    break, and every link anybody wrote down is the thing being protected.
    Somebody who chose badly gets an administrator, not a rename.
    """
    folded = check(wanted, floor=floor)

    if current_for(db, user_id) is not None:
        raise NameProblem(
            "You already have a name, and it cannot be changed. Contact "
            "support if there is a problem with it."
        )

    if holder(db, folded) is not None:
        # Deliberately the same answer whether it is held or revoked. "That
        # name was banned" tells somebody something about another person.
        raise NameProblem("Somebody already has that one.")

    row = ScreenName(
        user_id=user_id, name=folded, display=wanted.strip(), revoked=False
    )
    db.add(row)
    return row


def revoke(db: Session, name: str) -> ScreenName | None:
    """Take a name away, permanently.

    The row stays and stays unique, so the name is spent — the person who
    chose it cannot take it back and nobody else can pick it up. Their
    collection is untouched; they have simply lost the URL, and can claim a
    different name once.
    """
    from datetime import datetime, timezone

    row = holder(db, name)
    if row is None or row.revoked:
        return row
    row.revoked = True
    row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return row
