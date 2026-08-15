#!/bin/sh
# Migrate, optionally seed the card database, then serve.
set -e

alembic upgrade head

# First run has an empty catalog, which makes the app look broken. Seed it in
# the background so the UI is up immediately and fills in as cards land.
# SEED_ON_START=false skips it; re-running the seed later is always safe.
if [ "${SEED_ON_START:-true}" = "true" ]; then
  (
    if python /seed/seed_cards.py --check-empty; then
      echo "[seed] empty card catalog — downloading the full card database…"
      python /seed/seed_cards.py --download || echo "[seed] failed; run it by hand later"

      # Card pictures are seeded pointing at images.pokemontcg.io, which is
      # somebody else's CDN. One household is a rounding error there; serving
      # a whole site from it is not, so a shared install moves them onto
      # TCGdex's asset host, which is published for this. Off by default:
      # self-hosters are the rounding error, and this costs a few minutes of
      # requests they have no reason to spend.
      if [ "${CARD_ART:-}" = "tcgdex" ]; then
        echo "[seed] moving card art onto TCGdex…"
        python /seed/backfill_art.py || echo "[seed] art backfill failed; run it by hand later"
      fi
    fi
  ) &
fi

# 0.0.0.0 is every IPv4 address on this container, which is what compose
# networking uses and what every self-hosted install wants.
#
# Some platform hosts route between services over IPv6 only — Railway is one —
# and there an IPv4-only listener resolves, accepts nothing, and looks exactly
# like a crashed API from the container next door. Setting BIND_HOST=:: listens
# on IPv6 (and, on Linux defaults, IPv4 with it). Left alone nothing changes.
exec uvicorn app.main:app --host "${BIND_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
