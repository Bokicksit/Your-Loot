# Security

## Reporting a vulnerability

Please **don't** open a public issue for a security problem.

Use GitHub's [private vulnerability
reporting](https://github.com/Bokicksit/Your-Loot/security/advisories/new) —
Security tab → Report a vulnerability. It's private between you and the
maintainer until there's a fix.

Expect an acknowledgement within a few days. This is a one-person project, so
a fix takes as long as it takes, but you'll be told where it stands rather
than left guessing. Credit in the release notes unless you'd rather not.

## Supported versions

The latest tagged release. There is no backporting to older tags — if you're
affected, upgrade.

## What this app assumes about where it runs

Worth being explicit, because it changes what counts as a vulnerability.

**Authentication is optional, and off by default.** Out of the box, anyone
who can reach the port can read and edit the whole collection. That is a
choice for a single-user app on a home network, not an oversight, and "there
is no login screen by default" is not a vulnerability report. A way past one
that is supposed to be there very much is.

There are three states:

| | |
| --- | --- |
| **Default** | No login. The app signs itself in as the owner. |
| **Locked** (a password or PIN set in Settings) | One account, one password, no accounts to manage. |
| **`AUTH_MODE=multi`** | Accounts, each with their own collection off a shared catalog. |

Where two people share an install, they are properly separated — copies,
wanted list, binder, preferences and per-item photos and notes — and that is
covered by tests rather than by assertion.

**A lock is not a hardened front door, and you should still not expose this
to the internet.** What it is: enough to keep a housemate, a guest on your
wifi, or a curious browser on the LAN out of your collection. What it is
not:

- **There is no HTTPS unless you put some in front.** `SESSION_HTTPS_ONLY`
  defaults to false because plenty of these run on a LAN over plain http, and
  a secure-only cookie would silently never be sent. Over http, a session
  cookie travels in the clear.
- **A four-digit PIN is a four-digit PIN.** It is offered because it is what
  you want on a phone, and it is defensible because guessing is throttled —
  five wrong answers per address and account, then a five-minute wait — not
  because four digits is strong.
- **No lockout, no 2FA, no email verification.** The last is deliberate: an
  app you run yourself should not need an SMTP server before you can get back
  into it. `python -m app.resetpw` on the host is the recovery path, and shell
  access to the container is the credential, since whoever has it can read the
  database anyway.
- **It protects the app, not the data.** Anyone who can reach the host can
  read Postgres directly.

So: a VPN (Tailscale, WireGuard) or an authenticating reverse proxy is still
the answer for reaching this from outside. The lock is a second layer, not a
replacement for the first.

Cross-site request forgery is covered: the session cookie is `SameSite=Lax`
and every state-changing route is POST/PATCH/DELETE, so a form on another
site cannot ride your session.

**The API trusts its own network.** The api container expects to be reachable
only by the web container. The compose files don't publish its port for that
reason — if you publish it yourself, you've removed the boundary.

**Uploaded and fetched images are stored on disk and served back.** Uploads
are extension- and size-limited, and remote fetches refuse private and
loopback addresses to stop the server being used to probe your own network.
Holes in either of those are worth reporting.

**Integration keys sit in `.env` in plain text** and are readable by anyone
with shell access to the host, by design — that's how Docker environment
config works. Keep `.env` out of version control; the shipped `.gitignore`
already does.
