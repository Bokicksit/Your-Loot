# 💰 Your Loot

[![Release](https://img.shields.io/github/v/release/Bokicksit/Your-Loot?sort=semver)](https://github.com/Bokicksit/Your-Loot/releases)
[![Licence: AGPL v3](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)
[![Build](https://github.com/Bokicksit/Your-Loot/actions/workflows/build-push.yaml/badge.svg)](https://github.com/Bokicksit/Your-Loot/actions/workflows/build-push.yaml)
![amd64 + arm64](https://img.shields.io/badge/arch-amd64%20%7C%20arm64-informational)

Self-hosted collection tracker for **Pokémon cards, video games, hardware,
physical movies, books, records, LEGO, and comics** — one app, one database,
one wanted list that spans all of them.

Most trackers do a single category. This one is built for people whose shelf
isn't that tidy: the Charizard you're hunting and the SNES console you're
hunting live on the same list.

<p align="center">
  <img src="docs/screenshots/wanted.jpg" alt="One wanted list holding two Pokémon cards, five PlayStation games, a LEGO set and a Blu-ray" width="32%">
  <img src="docs/screenshots/games.jpg" alt="A shelf of Dreamcast games as cover tiles" width="32%">
  <img src="docs/screenshots/scan.jpg" alt="Scanning the barcode on a SNES box" width="32%">
</p>

<p align="center">
  <em>One wanted list across everything · your shelf as its own covers · and a
  barcode fills the rest in</em>
</p>

> [!IMPORTANT]
> **Out of the box there is no login screen** — it opens straight into your
> collection, which is what you want on a home network. Two ways to change
> that: set a password or PIN in **Settings → Lock this app**, or turn on
> `AUTH_MODE=multi` for real accounts.
>
> Either way, **still don't put it on the open internet.** A lock on the app
> is not the same as hardening a server. Use a VPN or an authenticating
> reverse proxy — see [SECURITY.md](SECURITY.md).

<p align="center">
  <img src="docs/screenshots/collections.jpg" alt="The collections you keep, with counts" width="52%">
</p>

📖 **[User Guide](docs/USER-GUIDE.md)** — how everything works, in depth:
adding items, barcode scanning, the binder, grading, backups, troubleshooting.

## What it does

**Cards** — search 20,000+ Pokémon cards by name, number, or set code (`151`,
`MEW`, `JTG`). Track each copy with condition and grading (PSA/BGS/CGC…). Cards
missing from the offline database can be pulled from an online catalog or
entered by hand with your own photo.

**Pokédex binder** — a slot per national dex number, mirroring a physical
binder: one card per Pokémon, marked either *the one* or *will upgrade*.
Filter by what's missing, what wants upgrading, and by rarity.

<p align="center">
  <img src="docs/screenshots/cards.jpg" alt="A card collection four across" width="46%">
  <img src="docs/screenshots/pokedex.jpg" alt="The Pokédex binder, part filled" width="46%">
</p>

**Games** — IGDB-backed search, platform/region, and per-copy completeness
(loose/CIB/sealed) and condition. Barcode scanning for boxed games. For
consoles up to the Xbox 360 era it also offers a **scan of the actual box**
from libretro-thumbnails — no key needed — instead of IGDB's key art, which
looks the same whether you own the original or a download.

**Hardware** — consoles and accessories with model number, serial, working
status, and accessory→console links.

**Movies** — TMDB-backed, with the physical details that matter: format
(4K/Blu-ray/DVD/VHS), edition, region code. Scanning the barcode also pulls
photographs of the actual case, so a steelbook looks like your steelbook
instead of the theatrical poster.

**Books** — Open Library search, or scan the ISBN barcode on the back. Format,
edition, series, and per-copy jacket/provenance. Graphic novels, collected
editions and manga live here rather than in Comics — they carry an ISBN, and
filtering to *Graphic Novel* sorted by series gives you that shelf in reading
order.

**Records** — MusicBrainz search, or scan the barcode on the sleeve, which
identifies the *pressing*: label, catalogue number, country, and year, so a
1980 original and a 2011 repress stay separate entries. Graded the way vinyl
actually is — media and sleeve independently, on the Goldmine scale (`VG+/VG`).

**LEGO** — Rebrickable-backed set search by number or name, with theme, year,
piece and minifig counts. Each copy answers two questions rather than one:
whether you kept the box, and what state the set is in — sealed, opened and
complete, loose bricks, built, or missing pieces. Sealed implies the box, and
the form won't let you say otherwise.

**Comics** — Comic Vine search by series and issue. Tracks the run
(`volume_year`) and the variant cover, because Amazing Spider-Man #1 exists in
half a dozen volumes. A raw copy carries a grade; a slabbed one carries its
CGC/CBCS number instead. Single issues — collected editions are books.

**Sold prices** — every item, owned or wanted, has a coin in its details panel
that opens an eBay search filtered to *sold and completed* listings. The query
is built from whatever separates two listings in that collection: the set and
number for a card, the model number for a console, the pressing format for a
record.

**Wanted list** — everything you're hunting, across every module, with
filters and the same sold-price shortcut. Mark something acquired and
it moves into your collection with the condition you set. Find only the case or
the manual and it records the spare while the game stays on the hunt.

**Accounts, if you want them** — nothing by default: the app opens straight
into your collection. Set a password or a short PIN in Settings and it asks
first, the way Radarr and Sonarr do. Or run with `AUTH_MODE=multi` for proper
accounts, where everyone gets their own copies, wanted list, binder and
Pokédex off one shared catalog. Passwords are argon2id, sessions are signed
http-only cookies, and repeated wrong guesses are throttled.

**Backup & restore** — Settings gives you a one-click zip of the whole
install: every item, every copy, the wanted list, the binder, your settings,
and your uploaded photos. Restoring replaces everything from that file. It's
plain JSON inside, so it stays readable and portable across Postgres versions.

## Quick start

```bash
git clone https://github.com/Bokicksit/Your-Loot.git && cd Your-Loot
cp .env.example .env      # set POSTGRES_PASSWORD
docker compose up -d
```

Open **http://localhost:8080**. It asks your name, then you're in.

The card database (~20k cards) downloads itself in the background on first
start — the app is usable immediately and cards appear within a few minutes.
Watch it if you like:

```bash
docker compose logs -f api
```

### Optional API keys

All free, all optional. Without one, that collection's online search says which
key is missing and manual entry still works. Cards, books and records need no
key at all.

| Key | For | Where |
| --- | --- | --- |
| `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET` | game search | [Twitch dev console](https://api-docs.igdb.com/#account-creation) |
| `TMDB_API_KEY` | movie search | [themoviedb.org](https://www.themoviedb.org/settings/api) |
| `REBRICKABLE_API_KEY` | LEGO set search | [rebrickable.com](https://rebrickable.com/users/_/settings/#api) → Account → Settings → API |
| `COMICVINE_API_KEY` | comic search | [comicvine.gamespot.com/api](https://comicvine.gamespot.com/api/) |
| `DISCOGS_TOKEN` | record barcodes | [discogs.com/settings/developers](https://www.discogs.com/settings/developers) → Generate token |

There's one more that isn't a key:

| Setting | Default | What it does |
| --- | --- | --- |
| `AUTH_MODE` | `single` | `single` = one collection, and a login only if you set a password in Settings. `multi` = accounts, each with their own collection. |

Add them to `.env` and `docker compose up -d` again.

## Keeping it running

**Update:**
```bash
docker compose pull && docker compose up -d
```
Database migrations run automatically. To update deliberately instead, pin a
version with `TAG=` in `.env` — the numbers are on the
[releases page](https://github.com/Bokicksit/Your-Loot/releases).

**Refresh the card database** (new sets, corrections) — weekly cron is plenty:
```bash
docker compose exec api python /seed/seed_cards.py --download
```
This only ever adds and updates catalog entries. Your owned copies, wanted
list, binder picks, grades, and any photos you added are never touched.

**Back up** from **Settings → Backup & restore** — one zip with every item,
copy, wanted entry and photo. Keep it somewhere that isn't this server. At the
filesystem level the `data/` directory holds the Postgres database and your
uploaded images; nothing else holds state.

## Remote access

Even with a password set, **don't expose port 8080 to the internet directly.**
The lock keeps a housemate out of your collection; it is not a hardened
front door, and there's no HTTPS unless you put some in front. Either:

- **Tailscale** — reach it privately from your phone, nothing public.
- **Cloudflare Tunnel + Access** — a real HTTPS hostname gated by your email.
  HTTPS also unlocks the barcode scanner, since browsers only allow camera
  access on secure origins.

## Running on TrueNAS SCALE

See [`deploy/compose.truenas.yaml`](deploy/compose.truenas.yaml) — paste it into
**Apps → Discover Apps → ⋮ → Install via YAML**, after editing the password and
dataset paths. It publishes port 30080, since 8080 is usually taken.

**To update it:** *Apps → Installed → Your Loot → Edit*, then **Save**. TrueNAS
pulls the images and recreates the containers — that's the whole update. The
`docker compose pull` in [Keeping it running](#keeping-it-running) is for
plain-Docker installs; a TrueNAS app is managed by TrueNAS, and running compose
against it by hand from a shell means fighting it for control of the stack.

**To check what's actually running**, open `http://<your-nas>:30080/api/health`
in a browser. That's the API's version; the bottom of the Settings page is the
web container's. **If the two disagree, one image updated and the other
didn't** — which looks like the app being broken rather than being half
upgraded, so it's worth checking first whenever something is behaving oddly
after an update.

## Development

```bash
docker compose -f compose.dev.yaml up --build
```
Builds from source instead of pulling images, exposes the API on :8000
(interactive docs at `/docs`), and skips the first-run seed. Frontend-only
work: `cd web && npm install && npm run dev`.

**Stack:** FastAPI + SQLAlchemy + Alembic + Postgres, React + Vite, nginx.
One `collection_item` table shared by every module, with per-module attribute
tables and separate `owned`/`wanted` records — which is why the wanted list can
span every category with a single query. Adding another module is a new
attributes table plus a router; nothing existing changes.

```
api/     FastAPI app, models, migrations, integrations (IGDB/TMDB/TCGdex/…)
web/     React SPA + nginx
seed/    offline card-database seeder
deploy/  TrueNAS compose
```

## Data sources & credits

- Card data: [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data)
  and [TCGdex](https://tcgdex.dev)
- Games: [IGDB](https://www.igdb.com), box scans from
  [libretro-thumbnails](https://github.com/libretro-thumbnails) ·
  Movies: [TMDB](https://www.themoviedb.org)
  (this product uses the TMDB API but is not endorsed or certified by TMDB)
- Books: [Open Library](https://openlibrary.org)
- Records: [MusicBrainz](https://musicbrainz.org) and the
  [Cover Art Archive](https://coverartarchive.org)
- LEGO: [Rebrickable](https://rebrickable.com) · Comics:
  [Comic Vine](https://comicvine.gamespot.com)
- Barcodes: [UPCitemdb](https://www.upcitemdb.com)
- Console logos: see [`web/public/platforms/ATTRIBUTION.md`](web/public/platforms/ATTRIBUTION.md)

Every integration is optional and free — see
[Optional API keys](#optional-api-keys).

Pokémon and all card imagery are property of Nintendo / Creatures Inc. /
GAME FREAK inc. and The Pokémon Company. This project is a personal collection
tool, unaffiliated with and unendorsed by any of them.

## License

[AGPL-3.0](LICENSE) — free to use, self-host, and modify. If you run a modified
version as a network service, you must publish your changes.
