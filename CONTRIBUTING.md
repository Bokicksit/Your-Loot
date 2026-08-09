# Contributing

Thanks for looking. This is a small project run by one person, so the most
useful thing you can do is usually not a pull request — read on.

## Bug reports are the best contribution

Genuinely. Most of what's wrong with this app is stuff that only shows up on
somebody else's shelf: a barcode that scans to the wrong edition, a set code
the card search doesn't know, a NAS that mounts its storage differently.

A good report has the version (bottom of the Settings page), what you did,
what happened, and what you expected. If it involves a specific item, the
barcode or catalogue number helps enormously — half these bugs are one weird
record in somebody else's database.

## Before you write code

**Open an issue first.** Not bureaucracy — this app has strong opinions about
how a collection is modelled (a shared catalogue, per-copy ownership, the
owned/wanted split), and a patch that cuts across those takes longer to
discuss after it's written than before. A short issue saves you the work.

## The CLA, and why there is one

Code contributions need a signed [Contributor Licence Agreement](CLA.md). A
bot asks on your first pull request and you sign by replying to it with one
line — no account, no form, nothing to email.

Here's the honest reason, because "our lawyers require it" is not a reason:

**Your Loot is free and AGPL-3.0, and that isn't changing.** But there is
also going to be a hosted version for people who don't want to run Docker,
and a mobile app in the app stores. The app stores are the problem — their
distribution terms are incompatible with GPL-family licences, which is why
VLC was once pulled from the App Store. Today I wrote every line, so I can
license my own code to Apple on separate terms and the AGPL release is
unaffected. The moment someone else's AGPL-only code is in the tree, that
stops being possible and the mobile app dies.

The CLA fixes that by letting me license contributions under other terms too.
What it does **not** do is take anything away from you: you keep your
copyright, and everything here stays AGPL for everyone, forever.

If you'd rather not sign — that's completely fair, and the asymmetry people
object to is real. Open an issue describing the fix instead. That's still a
contribution, and it still gets you credited in the release notes.

## Running it locally

```bash
cp .env.example .env      # set POSTGRES_PASSWORD
docker compose -f compose.dev.yaml up --build
```

The API is on :8000 with docs at `/docs`, the web app on :5173 with hot
reload. Integration keys are all optional — every collection works without
them, you just lose online search for that category.

## Tests

```bash
docker compose -f compose.test.yaml run --rm tests
```

Its own stack, its own database, storage that dies with the container. That
separation is deliberate: restoring a backup replaces the entire database, so
the suite that exercises it must not be one flag away from doing that to the
install holding somebody's actual collection. The destructive tests refuse to
run unless `LOOT_DESTRUCTIVE_OK=1`, which only `compose.test.yaml` sets.

Three things are covered, in order of how much they'd hurt:

- **Migrations** reverse and re-apply without losing data. This one runs
  safely anywhere — it builds and drops its own scratch database — and it's
  the one protecting people you'll never meet from an upgrade at midnight.
- **Backup and restore** actually round-trips, including per-copy condition
  and notes, and refuses a corrupt file rather than half-applying it.
- **Tenancy**: two real accounts, and nothing of one appears anywhere in the
  other's answers.

CI runs all of it, and no image is published unless it passes.

## House style

The code is commented, but for *why* rather than *what*. A comment explaining
that a loop iterates is noise; a comment explaining that libretro files games
under No-Intro naming so the titles never match directly is the reason the
next person doesn't "simplify" it into a bug. Match what's around you.

Commit subjects are written as sentences, not conventional-commit prefixes.

## Releases

`VERSION` moves +0.01 per commit and is baked into the image tag, so any
build is traceable to a commit. Tagged releases are the ones meant for
pinning.
