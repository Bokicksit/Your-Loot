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

**Your Loot has no authentication.** Anyone who can reach the port can read
and edit the entire collection. That's a deliberate choice for a single-user
app on a home network, not an oversight — and it means **you must not expose
it directly to the internet.** Put it behind a VPN (Tailscale, WireGuard) or
an authenticating reverse proxy. "No login screen" is not a vulnerability
report; a way to get past one that's supposed to be there is.

*(Optional user accounts are the next thing being built. Until then, the
above holds.)*

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
