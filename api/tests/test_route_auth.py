"""Is there a route nobody has to sign in to reach?

This exists because four of them were, and nothing noticed. `/api/images`
and `/api/images/fetch` took an upload and fetched a URL for anybody on the
internet; `/api/lookup/*` spent the barcode quota for them. None of it was
carelessness — those endpoints were written when this ran on a home network
where "anybody" meant the household. They became a problem the day it faced
the internet, and no test failed, because nothing tests for an absence.

So this walks every route the app registers and asks each one whether it
requires a person. Anything that does not has to be named below, on purpose,
with a reason. A new endpoint that forgets fails here rather than in the
wild.

    docker compose -f compose.test.yaml run --rm tests
"""

import pytest
from fastapi.routing import APIRoute

from app.auth import current_user, require_admin
from app.main import app

# Routes that genuinely must answer a stranger, each for a stated reason.
# Adding to this list should feel like a decision, which is why it is a list
# of reasons rather than a list of paths.
PUBLIC = {
    ("GET", "/api/health"): "liveness — the container orchestrator has no account",
    ("GET", "/api/auth/me"): "what screen to draw; answers 'nobody' rather than 401",
    ("POST", "/api/auth/setup"): "claims the first account, before anybody exists",
    ("POST", "/api/auth/login"): "the door itself",
    ("POST", "/api/auth/logout"): "harmless, and must work with a dead session",
    ("POST", "/api/auth/signup"): "makes the account; gated on OPEN_SIGNUP instead",
    ("POST", "/api/auth/verify"): "the token in the emailed link is the credential",
    ("POST", "/api/auth/forgot"): "asked by somebody who cannot sign in",
    ("POST", "/api/auth/reset"): "same — the emailed token is the credential",
    ("POST", "/api/billing/webhook"): "Stripe has no session; the signature is the proof",
    ("GET", "/images/{name}"): "a session or a signed token, checked inside the handler",
}


GUARDS = (current_user, require_admin)


def _walk(routes, inherited=()):
    """Every real route, with any guard attached where it was included.

    This version of FastAPI does not flatten included routers into app.routes
    — it keeps a wrapper holding the original router and the arguments it was
    included with. So the routes have to be reached through that, and the
    dependencies passed to include_router have to be carried down, or a
    router guarded as a whole would read as unguarded.
    """
    for r in routes:
        if isinstance(r, APIRoute):
            yield r, list(inherited)
            continue
        inner = getattr(r, "original_router", None)
        if inner is not None and hasattr(inner, "routes"):
            ctx = getattr(r, "include_context", None)
            here = list(getattr(ctx, "dependencies", None) or [])
            yield from _walk(inner.routes, list(inherited) + here)
        elif hasattr(r, "routes"):  # plain Mount, or a future flattened shape
            yield from _walk(r.routes, inherited)


def _wants_a_person(route: APIRoute, inherited=()) -> bool:
    """Does anything guarding this route reach current_user or require_admin?

    Walked rather than pattern-matched on source, because the guard arrives
    three ways — on the handler, on the router, or on include_router — and a
    check that understood only one would pass while the door stood open.
    """
    for dep in inherited:
        if getattr(dep, "dependency", None) in GUARDS:
            return True

    seen, stack = set(), list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        if dep.call in GUARDS:
            return True
        stack.extend(dep.dependencies)
    return False


def _routes():
    for route, inherited in _walk(app.routes):
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield method, route.path, route, inherited


def test_every_route_needs_a_person_or_says_why_not():
    open_doors = [
        f"{method} {path}"
        for method, path, route, inherited in _routes()
        if not _wants_a_person(route, inherited) and (method, path) not in PUBLIC
    ]
    assert not open_doors, (
        "these answer anybody on the internet:\n  "
        + "\n  ".join(sorted(open_doors))
        + "\n\nAdd Depends(current_user), or add it to PUBLIC with a reason."
    )


def test_the_four_that_were_open_are_shut():
    """Named individually so the regression is unmistakable rather than
    buried in a count."""
    guarded = {
        (m, p) for m, p, r, inh in _routes() if _wants_a_person(r, inh)
    }
    for method, path in [
        ("POST", "/api/images"),
        ("POST", "/api/images/fetch"),
        ("GET", "/api/lookup/barcode"),
        ("GET", "/api/lookup/products"),
    ]:
        assert (method, path) in guarded, f"{method} {path} is open again"


def test_the_public_list_has_no_stale_entries():
    """A path that no longer exists should not sit here looking like an
    exemption somebody still needs."""
    real = {(m, p) for m, p, _r, _i in _routes()}
    stale = [f"{m} {p}" for (m, p) in PUBLIC if (m, p) not in real]
    assert not stale, f"PUBLIC lists routes that are gone: {stale}"
