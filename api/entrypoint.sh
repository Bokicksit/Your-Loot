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
    fi
  ) &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
