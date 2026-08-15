"""Can somebody make themselves an account, prove it is theirs, and leave?

Three properties matter more than the happy path:

* a self-hosted install must not grow a signup form because this code exists;
* /forgot must answer identically for an address that has an account and one
  that does not, or it becomes a way to ask who uses the service;
* deleting an account must actually take the collection with it.

No mail provider runs in the suite — that is the point, since neither does one
on most installs. The links are therefore issued straight into the same
database the API reads, which tests the redeeming without pretending to test
somebody else's SMTP.

    docker compose -f compose.test.yaml run --rm tests
"""

import os
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.auth import OWNER_ID, RESET_MINUTES, VERIFY_HOURS, issue_link_token
from app.models import AuthToken, Owned, User

BASE = os.environ.get("LOOT_URL", "http://localhost:8000")
OPEN = os.environ.get("LOOT_OPEN_URL")
SOLO = os.environ.get("LOOT_SOLO_URL")
OPEN_DB = os.environ.get("OPEN_DATABASE_URL")

needs_open = pytest.mark.skipif(not OPEN, reason="no open-signup API configured")

PASSWORD = "a-real-password-1"
OWNER_PASSWORD = "the-owner-password-1"


@pytest.fixture(scope="module", autouse=True)
def owner_of_open():
    """Claim id 1 before any signup does.

    Session-scoped and first, because /setup only works while no account has
    a password — so if a signup gets there first, the owner is whoever that
    was and this module can no longer test the guard on it.
    """
    if not OPEN:
        yield None
        return
    c = httpx.Client(base_url=OPEN, timeout=60)
    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    me = c.get("/api/auth/me").json()
    if me.get("needs_setup"):
        c.post(
            "/api/auth/setup", json={"email": email, "password": OWNER_PASSWORD}
        ).raise_for_status()
    else:
        c.post(
            "/api/auth/login", json={"email": email, "password": OWNER_PASSWORD}
        )
    yield c, email
    c.close()


@pytest.fixture
def odb():
    """A session on the open-signup API's database — the one it reads."""
    if not OPEN_DB:
        pytest.skip("no OPEN_DATABASE_URL")
    engine = create_engine(OPEN_DB)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


def an_email() -> str:
    return f"person-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def signed_up():
    """A fresh account on the open API, with its client. Cleaned up after."""
    c = httpx.Client(base_url=OPEN, timeout=60)
    email = an_email()
    r = c.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    yield c, email, r.json()
    c.close()


def _user(odb, email):
    return odb.query(User).filter(User.email == email).one_or_none()


# --- the install that should not have grown a signup form ------------------


def test_signup_is_off_unless_it_is_turned_on():
    """The default multi-user install is somebody's home server with invited
    accounts. A stranger who finds it must not be able to make one."""
    r = httpx.post(
        f"{BASE}/api/auth/signup",
        json={"email": an_email(), "password": PASSWORD},
        timeout=60,
    )
    assert r.status_code == 404, "an invite-only install offered open signup"


def test_a_server_with_no_mail_provider_offers_no_reset():
    """The install this actually protects: somebody's house, accounts on for
    the family, no mail provider and no wish for one.

    Without this, /forgot answers 204 and quietly writes a working reset link
    into the container log for anybody who asks — reachable by whoever can
    reach the API. The password is reset from the host there, which is what
    the sign-in screen says.
    """
    me = httpx.get(f"{BASE}/api/auth/me", timeout=60).json()
    assert me["email_enabled"] is False, "the invite-only test stack grew a mail provider"

    r = httpx.post(f"{BASE}/api/auth/forgot", json={"email": an_email()}, timeout=60)
    assert r.status_code == 404, "a reset was offered with nowhere to send it"


@needs_open
def test_the_two_flags_are_separate_questions():
    """Whether strangers may join and whether this server can send mail were
    the same flag once. A family install with a provider wants resets without
    wanting signups, and the UI branches on each of them separately."""
    me = httpx.get(f"{OPEN}/api/auth/me", timeout=60).json()
    assert me["open_signup"] is True
    assert me["email_enabled"] is True

    invite_only = httpx.get(f"{BASE}/api/auth/me", timeout=60).json()
    assert invite_only["open_signup"] is False
    assert invite_only["email_enabled"] is False


@pytest.mark.skipif(not SOLO, reason="no single-user API configured")
def test_a_single_user_install_has_none_of_this():
    for path, body in [
        ("/api/auth/signup", {"email": an_email(), "password": PASSWORD}),
        ("/api/auth/forgot", {"email": an_email()}),
    ]:
        r = httpx.post(f"{SOLO}{path}", json=body, timeout=60)
        assert r.status_code == 404, f"{path} answered {r.status_code} in single-user mode"


# --- signing up ------------------------------------------------------------


@needs_open
def test_a_person_can_sign_themselves_up(signed_up, odb):
    _c, email, body = signed_up
    assert body["email"] == email
    assert body["is_admin"] is False, "a self-made account should not be an admin"
    assert body["email_verified_at"] is None, "signing up is not proof of an address"
    assert _user(odb, email) is not None


@needs_open
def test_signing_up_signs_you_in(signed_up):
    c, email, _ = signed_up
    me = c.get("/api/auth/me").json()
    assert me["user"] and me["user"]["email"] == email, \
        "a new account had to sign in again immediately"


@needs_open
def test_the_same_address_cannot_sign_up_twice(signed_up):
    _c, email, _ = signed_up
    r = httpx.post(
        f"{OPEN}/api/auth/signup", json={"email": email, "password": PASSWORD}, timeout=60
    )
    assert r.status_code == 409


# --- proving the address is yours ------------------------------------------


@needs_open
def test_a_verification_link_works_once(signed_up, odb):
    c, email, _ = signed_up
    raw = issue_link_token(odb, _user(odb, email), AuthToken.VERIFY,
                           timedelta(hours=VERIFY_HOURS))

    assert httpx.post(f"{OPEN}/api/auth/verify", json={"token": raw}, timeout=60).status_code == 204
    assert c.get("/api/auth/me").json()["user"]["email_verified_at"] is not None

    again = httpx.post(f"{OPEN}/api/auth/verify", json={"token": raw}, timeout=60)
    assert again.status_code == 400, "a spent link was accepted a second time"


@needs_open
def test_an_expired_link_is_refused(signed_up, odb):
    _c, email, _ = signed_up
    raw = issue_link_token(odb, _user(odb, email), AuthToken.VERIFY,
                           timedelta(seconds=-1))
    r = httpx.post(f"{OPEN}/api/auth/verify", json={"token": raw}, timeout=60)
    assert r.status_code == 400


@needs_open
def test_asking_for_a_new_link_kills_the_old_one(signed_up, odb):
    """Otherwise a link you replaced because it went to the wrong place stays
    live for a day after you replaced it."""
    _c, email, _ = signed_up
    user = _user(odb, email)
    first = issue_link_token(odb, user, AuthToken.VERIFY, timedelta(hours=VERIFY_HOURS))
    second = issue_link_token(odb, user, AuthToken.VERIFY, timedelta(hours=VERIFY_HOURS))

    assert httpx.post(f"{OPEN}/api/auth/verify", json={"token": first}, timeout=60).status_code == 400
    assert httpx.post(f"{OPEN}/api/auth/verify", json={"token": second}, timeout=60).status_code == 204


@needs_open
def test_a_verify_link_cannot_reset_a_password(signed_up, odb):
    """The two kinds share a table. They must not share a meaning."""
    _c, email, _ = signed_up
    raw = issue_link_token(odb, _user(odb, email), AuthToken.VERIFY,
                           timedelta(hours=VERIFY_HOURS))
    r = httpx.post(
        f"{OPEN}/api/auth/reset", json={"token": raw, "password": "something-else-1"},
        timeout=60,
    )
    assert r.status_code == 400, "a verification link was accepted as a password reset"


# --- forgetting your password ----------------------------------------------


@needs_open
def test_forgot_says_the_same_thing_about_everybody(signed_up):
    """An address with an account and one without must be indistinguishable,
    or this is a way to ask which of a list of people uses the service."""
    _c, email, _ = signed_up
    real = httpx.post(f"{OPEN}/api/auth/forgot", json={"email": email}, timeout=60)
    fake = httpx.post(f"{OPEN}/api/auth/forgot", json={"email": an_email()}, timeout=60)

    assert real.status_code == fake.status_code == 204
    assert real.text == fake.text


@needs_open
def test_a_reset_link_changes_the_password(signed_up, odb):
    _c, email, _ = signed_up
    raw = issue_link_token(odb, _user(odb, email), AuthToken.RESET,
                           timedelta(minutes=RESET_MINUTES))
    new = "a-different-password-2"

    r = httpx.post(f"{OPEN}/api/auth/reset", json={"token": raw, "password": new}, timeout=60)
    assert r.status_code == 204

    fresh = httpx.Client(base_url=OPEN, timeout=60)
    try:
        assert fresh.post("/api/auth/login", json={"email": email, "password": new}).status_code == 200
        assert fresh.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code == 401, "the old password still worked after a reset"
    finally:
        fresh.close()


@needs_open
def test_resetting_also_proves_the_address(signed_up, odb):
    """Reading the mailbox is exactly the proof verification asks for."""
    _c, email, _ = signed_up
    raw = issue_link_token(odb, _user(odb, email), AuthToken.RESET,
                           timedelta(minutes=RESET_MINUTES))
    httpx.post(f"{OPEN}/api/auth/reset", json={"token": raw, "password": "yet-another-3"},
               timeout=60).raise_for_status()

    odb.expire_all()
    assert _user(odb, email).email_verified_at is not None


# --- leaving ---------------------------------------------------------------


@needs_open
def test_deleting_your_account_takes_your_collection(signed_up, odb):
    c, email, body = signed_up
    uid = body["id"]

    item = c.post("/api/games", json={"title": f"Game {uuid.uuid4().hex[:6]}"})
    item.raise_for_status()
    c.post(f"/api/items/{item.json()['id']}/owned", json={"condition": "NM"}).raise_for_status()
    assert odb.scalar(select(func.count()).select_from(Owned).where(Owned.user_id == uid)) == 1

    r = c.request("DELETE", "/api/auth/me", json={"password": PASSWORD})
    assert r.status_code == 204

    odb.expire_all()
    assert _user(odb, email) is None, "the account survived its own deletion"
    assert odb.scalar(select(func.count()).select_from(Owned).where(Owned.user_id == uid)) == 0, \
        "the collection outlived the account"


@needs_open
def test_deleting_needs_the_right_password(signed_up, odb):
    c, email, _ = signed_up
    r = c.request("DELETE", "/api/auth/me", json={"password": "not-the-password"})
    assert r.status_code == 403
    assert _user(odb, email) is not None, "a wrong password still deleted the account"


@needs_open
def test_the_owner_cannot_delete_themselves(owner_of_open):
    """Deleting user 1 would leave a database nobody can sign into.

    Worth knowing when deploying: whoever holds id 1 cannot leave, so the
    owner account should be claimed through /setup before signup is opened,
    or the first stranger through the door becomes the undeletable one.
    """
    c, _email = owner_of_open
    assert c.get("/api/auth/me").json()["user"]["id"] == OWNER_ID
    r = c.request("DELETE", "/api/auth/me", json={"password": OWNER_PASSWORD})
    assert r.status_code == 400
