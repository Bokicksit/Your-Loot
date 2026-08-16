"""Sending the two emails this app has any business sending.

Verify your address, and reset your password. Nothing else — no digests, no
announcements, no "we miss you". A collection tracker that emails you about
your collection is a collection tracker you stop using.

**Without a key this does not fail, it logs.** Almost every install of this
is one person on a home server who has no mail provider and does not want
one, and for them the whole feature is unnecessary: they set their password
directly and there is nobody to invite. So an absent RESEND_API_KEY prints
the link to the container log instead of raising, which also happens to be
exactly what you want while developing.

That has one consequence worth being deliberate about: on a keyless install
a password reset link appears in the logs, where anyone who can read the
logs can use it. That is the correct trade for a machine in somebody's
house, and it is the reason open signup is off by default — see routers/auth.
"""

import logging

import httpx

from app.config import settings

log = logging.getLogger("yourloot.mail")

# Plain text, deliberately. These are two short transactional messages; HTML
# would buy nothing and cost deliverability, and a link somebody can read
# before clicking is a feature in an email about their password.
VERIFY_SUBJECT = "Confirm your email"
RESET_SUBJECT = "Reset your password"

# Every sentence here has to be true, and getting there took two goes. The
# first said no account would be created without confirming, which was false.
# The second said confirming was what enabled a password reset, which was
# also false — /forgot has always answered a confirmed address and an
# unconfirmed one alike, and gating it would lock out anybody who mistyped
# their address. Now confirming does gate one real thing, and that is what it
# says.
VERIFY_BODY = """\
Welcome to Your Loot.

Your account is ready — you can start adding things straight away, and the
whole card side is free for good.

Confirming this address tells us we can reach you. You'll need it before
subscribing, since that's how a receipt or a renewal notice gets to you:

{link}

The link works for {hours} hours.

If you didn't sign up, somebody has used your address by mistake or on
purpose. Don't confirm it — and if you'd like that account removed, reply to
this message and we'll delete it.
"""

RESET_BODY = """\
Somebody asked to reset the password for this address.

{link}

The link works for {minutes} minutes and can only be used once. If it wasn't
you, nothing has changed and you can ignore this.
"""


def configured() -> bool:
    return bool(settings.resend_api_key and settings.mail_from)


def send(to: str, subject: str, body: str) -> bool:
    """True if a provider actually accepted it.

    Never raises. A signup that works but whose email fails is recoverable —
    they can ask for another one — while a signup that 500s because the mail
    provider is having an afternoon is not.
    """
    if not configured():
        log.warning(
            "no mail provider configured; %s for %s was not sent. Body:\n%s",
            subject, to, body,
        )
        return False

    try:
        resp = httpx.post(
            settings.mail_api_url,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.mail_from,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        # the address is worth logging, the token in the body is not
        log.error("could not send %r to %s: %s", subject, to, e)
        return False


def _link(path: str, token: str) -> str:
    return f"{settings.public_url.rstrip('/')}/{path.lstrip('/')}?token={token}"


def send_verification(to: str, token: str, hours: int) -> bool:
    return send(
        to, VERIFY_SUBJECT, VERIFY_BODY.format(link=_link("verify", token), hours=hours)
    )


def send_reset(to: str, token: str, minutes: int) -> bool:
    return send(
        to, RESET_SUBJECT, RESET_BODY.format(link=_link("reset", token), minutes=minutes)
    )
