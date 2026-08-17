"""What a free account gets on a service that costs money to run.

None of this exists on a self-hosted install, and that is the whole argument
rather than a footnote. The software is free and complete — anybody can run
it themselves, for nothing, forever, and get every card and every binder.
What costs money is somebody else running it for you: a server, a database,
a disk full of photographs and a bill at the end of the month.

So the limits here are all zero by default, meaning no limit, which is what
every existing install has and what every self-hoster keeps. A hosted
service sets them, and pays for the difference.

Three of them, and each is a number rather than a feature switch, because
taking a feature away makes the free tier a demo while capping one keeps it
a usable thing that happens to have an edge.
"""

from app.config import settings
from app.models import User
from app.plans import subscribed

# 0 everywhere means "no limit". Not None, because these come from the
# environment as strings and an unset number is naturally zero.
UNLIMITED = 0


def card_limit() -> int:
    """Copies of cards a free account may own."""
    return max(0, settings.free_card_limit)


def dex_limit() -> int:
    """How far up the Pokédex a free account can see. 151 is the first
    generation, which is a line people already recognise."""
    return max(0, settings.free_dex_limit)


def binder_limit() -> int:
    """Binders beyond the Pokédex — custom or master set, their choice."""
    return max(0, settings.free_binder_limit)


def cards_held(db, user_id: int) -> int:
    """Copies of cards this person owns, for the free-plan count.

    A card is a card. A Japanese printing costs the same to store, sits in
    the same binders and counts the same as an English one — which is why
    nothing here looks at `language` or at where the row was seeded from,
    and why it never should. Whether Japanese is worth having is a question
    about the catalogue, not about the bill.

    Its own function so the rule is written once. It was inline in the add
    handler, where the only way to say "and this counts Japanese too" would
    have been to test the handler's HTTP behaviour and hope the reason
    survived.
    """
    from sqlalchemy import func, select

    from app.models import CollectionItem, Module, Owned

    return db.scalar(
        select(func.count())
        .select_from(Owned)
        .join(CollectionItem, CollectionItem.id == Owned.item_id)
        .where(
            Owned.user_id == user_id,
            CollectionItem.module == Module.cards.value,
        )
    ) or 0


def limited(user: User) -> bool:
    """Is this person subject to any of it?

    False on every self-hosted install, because nothing is set there. False
    for anybody who has paid, and for admins, who are never billed.
    """
    if not any((card_limit(), dex_limit(), binder_limit())):
        return False
    return not subscribed(user)


def dex_ceiling(user: User) -> int:
    """The highest Pokédex number this person's binder should show."""
    from app.binder_view import MAX_DEX

    if not limited(user) or not dex_limit():
        return MAX_DEX
    return min(dex_limit(), MAX_DEX)
