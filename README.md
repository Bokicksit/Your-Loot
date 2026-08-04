# 💰 Your Loot

Self-hosted collection tracker for **Pokémon cards, video games, hardware, and
physical movies** — one app, one database, one wanted list that spans all of
them.

Most trackers do a single category. This one is built for people whose shelf
isn't that tidy: the Charizard you're hunting and the SNES console you're
hunting live on the same list.

*(screenshots go here)*

## What it does

**Cards** — search 20,000+ Pokémon cards by name, number, or set code (`151`,
`MEW`, `JTG`). Track each copy with condition and grading (PSA/BGS/CGC…). Cards
missing from the offline database can be pulled from an online catalog or
entered by hand with your own photo.

**Pokédex binder** — a slot per national dex number, mirroring a physical
binder: one card per Pokémon, marked either *the one* or *will upgrade*.
Filter by what's missing, what wants upgrading, and by rarity.

**Games** — IGDB-backed search, platform/region, and per-copy completeness
(loose/CIB/sealed) and condition. Barcode scanning for boxed games.

**Hardware** — consoles and accessories with model number, serial, working
status, and accessory→console links.

**Movies** — TMDB-backed, with the physical details that matter: format
(4K/Blu-ray/DVD/VHS), edition, region code.

**Wanted list** — everything you're hunting, across all four modules, with
filters and a "check sold prices on eBay" shortcut. Mark something acquired and
it moves into your collection with the condition you set.

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

Everything works without these; the affected search just says it isn't
configured, and manual entry still works.

| Key | For | Where |
| --- | --- | --- |
| `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET` | game search | [Twitch dev console](https://api-docs.igdb.com/#account-creation) (free) |
| `TMDB_API_KEY` | movie search | [themoviedb.org](https://www.themoviedb.org/settings/api) (free) |

Add them to `.env` and `docker compose up -d` again.

## Keeping it running

**Update:**
```bash
docker compose pull && docker compose up -d
```
Database migrations run automatically. Pin a version with `TAG=1.34` in `.env`
if you'd rather update deliberately.

**Refresh the card database** (new sets, corrections) — weekly cron is plenty:
```bash
docker compose exec api python /seed/seed_cards.py --download
```
This only ever adds and updates catalog entries. Your owned copies, wanted
list, binder picks, grades, and any photos you added are never touched.

**Back up** the `data/` directory — that's the Postgres database and your
uploaded images. Nothing else holds state.

## Remote access

The app has **no login of its own**, so don't expose port 8080 to the internet
directly. Either:

- **Tailscale** — reach it privately from your phone, nothing public.
- **Cloudflare Tunnel + Access** — a real HTTPS hostname gated by your email.
  HTTPS also unlocks the barcode scanner, since browsers only allow camera
  access on secure origins.

## Running on TrueNAS SCALE

See [`deploy/compose.truenas.yaml`](deploy/compose.truenas.yaml) — paste it into
**Apps → Discover Apps → ⋮ → Install via YAML**, after editing the password and
dataset paths. It publishes port 30080, since 8080 is usually taken.

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
span all four categories with a single query. Adding a fifth module is a new
attributes table plus a router; nothing existing changes.

```
api/     FastAPI app, models, migrations, integrations (IGDB/TMDB/TCGdex)
web/     React SPA + nginx
seed/    offline card-database seeder
deploy/  TrueNAS compose
```

## Data sources & credits

- Card data: [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data)
  and [TCGdex](https://tcgdex.dev)
- Games: [IGDB](https://www.igdb.com) · Movies: [TMDB](https://www.themoviedb.org)
  (this product uses the TMDB API but is not endorsed or certified by TMDB)
- Barcodes: [UPCitemdb](https://www.upcitemdb.com)
- Console logos: see [`web/public/platforms/ATTRIBUTION.md`](web/public/platforms/ATTRIBUTION.md)

Pokémon and all card imagery are property of Nintendo / Creatures Inc. /
GAME FREAK inc. and The Pokémon Company. This project is a personal collection
tool, unaffiliated with and unendorsed by any of them.

## License

[AGPL-3.0](LICENSE) — free to use, self-host, and modify. If you run a modified
version as a network service, you must publish your changes.
