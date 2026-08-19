"""Which collections this particular install offers at all.

Two different questions live near each other and were one list until now:

* what this *deployment* offers — a hosted service cannot legally carry
  movies or comics, because those catalogues forbid commercial use outright;
* what a *person* has switched on — their own preference, chosen from
  whatever the deployment offers.

The second was already a setting. This is the first, and it has to be
enforced on the API rather than merely hidden in the UI: a collection that is
absent from the tab bar but still answers on /api/movies is not absent, it is
just harder to find.

Empty means everything, so a self-hosted install sets nothing and keeps all
eight. That is the default and always will be — none of this is about them.
"""

from app.config import settings

# Every collection the code knows how to draw. Order is the order they appear.
ALL = [
    "cards", "amiibo", "games", "hardware", "movies", "books", "records",
    "lego", "comics",
]


def available() -> list[str]:
    """The collections this install offers, in the canonical order.

    An unknown name in the setting is ignored rather than fatal — a typo
    should cost you that one collection, not the ability to start the server.
    """
    named = [m.strip().lower() for m in settings.available_modules.split(",") if m.strip()]
    if not named:
        return list(ALL)
    return [m for m in ALL if m in named]


def offers(module: str) -> bool:
    return module in available()
