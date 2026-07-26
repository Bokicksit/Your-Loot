# 💰 Get Loot

Self-hosted collection tracker: Pokémon cards, video games & hardware, physical
movies — one app, one database, one cross-module wanted list.

**Phase 1 status:** Cards module is fully working (seed → search → own/want →
Pokédex grid). Games and Movies have schema, API stubs, and placeholder pages.

## Architecture

- **api** — FastAPI + SQLAlchemy + Alembic. Shared `collection_item` table with
  per-module attribute tables (`card_attrs`, `game_attrs`, `movie_attrs`).
  `owned` (one row per copy, with condition/completeness) and `wanted` reference
  items directly, so the wanted list is one query across all modules.
- **web** — React + Vite SPA, served by nginx which also proxies `/api` and
  `/images` to the api container. Mobile-first (bottom tab bar).
- **postgres** — data on a bind-mounted path so it maps to a TrueNAS dataset.

Adding a fourth module later: new attrs table + migration, new router, new page.
No changes to existing tables.

## Local dev

```bash
cp .env.example .env        # edit POSTGRES_PASSWORD at minimum
docker compose up --build
```

- Web UI: http://localhost:8080
- API docs: http://localhost:8000/docs

Seed the sample card set (committed in `seed/sample`, no network needed):

```bash
docker compose exec api python /seed/seed_cards.py
```

Full card database refresh (pulls the [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data)
dump): see `seed/refresh_cards.sh` — stubbed for a monthly cron job, safe to
re-run (upserts by card id, never touches owned/wanted).

Frontend-only iteration without docker: run the api once via compose, then
`cd web && npm install && npm run dev` (vite proxies `/api` to localhost:8000).

## Build & publish images (GHCR)

Pushing to `main` triggers `.github/workflows/build-push.yaml`, which builds
`getloot-api` and `getloot-web` and pushes them to
`ghcr.io/<your-user>/getloot-{api,web}` tagged with the git SHA and `latest`.
It authenticates with the built-in `GITHUB_TOKEN` — no secrets to configure.

One-time: after the first push, the GHCR packages may default to private. For
TrueNAS to pull without credentials, set them public (GitHub → your profile →
Packages → package settings → Change visibility), or add GHCR login on TrueNAS.

## Deploy on TrueNAS SCALE

1. Create two datasets, e.g. `tank/apps/getloot/postgres` and
   `tank/apps/getloot/images`.
2. Open `deploy/compose.truenas.yaml`, replace `YOURUSER`, `CHANGE_ME`, and the
   `/mnt/tank/...` paths.
3. TrueNAS UI → **Apps → Discover Apps → ⋮ → Install via YAML**, paste the
   file, save. Migrations run automatically on api start.
4. Seed the card data once:
   `docker exec getloot-api python /seed/seed_cards.py` (from the TrueNAS shell).
5. App is at `http://<nas-ip>:8080`.

To update after a push to main: re-deploy the app so it pulls fresh `:latest`
images (or pin a `sha-…` tag in the YAML for explicit upgrades).

### Remote access

Don't port-forward 8080 raw. Two good options (not configured here):

- **Tailscale** — simplest: run the Tailscale app on TrueNAS, access
  `http://<tailscale-ip>:8080` from your devices. Private by default.
- **Cloudflare Tunnel** — public HTTPS URL without opening ports; run
  `cloudflared` as another TrueNAS app pointing at the web service. Put
  Cloudflare Access in front since the app has no auth yet.

## Repo layout

```
api/         FastAPI app, models, Alembic migrations, integration stubs (IGDB/TMDB)
web/         React SPA + nginx
seed/        offline card seed script + sample data + refresh cron stub
deploy/      compose.truenas.yaml (pull-only deployment)
.github/     GHCR build workflow
```
