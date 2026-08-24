#!/bin/sh
# Migrate, optionally seed the card database, then serve.
set -e

alembic upgrade head

# The hardware catalogue ships inside the image (seed/data/consoles-na.json,
# our own dataset), so this needs no network and takes well under a second
# for 173 rows. On every start rather than first run only: idempotent, and a
# dataset correction in a release reaches every install without anybody
# remembering a command. Non-fatal, because a broken catalogue seed should
# never keep a working collection offline.
python /seed/seed_consoles.py || echo "[seed] console catalogue failed; run it by hand later"

# The card scanner's homework: fingerprint any card art that has none yet
# (seed/hash_cards.py), so a photograph can be matched against the catalogue.
# Off by default — the first run is twenty thousand fetches from TCGdex's
# CDN, which an operator should choose to start — but once opted in, every
# restart quietly does only the cards added since, which is how a new set
# becomes scannable without anybody remembering a command. A fully
# fingerprinted catalogue costs one database question and exits.
hash_art() {
  if [ "${HASH_CARD_ART:-false}" = "true" ]; then
    python /seed/hash_cards.py || echo "[seed] art fingerprints failed; run hash_cards.py by hand later"
  fi
}

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

    # The Japanese catalogue: 13,000 more cards, off unless asked for. It is
    # a separate switch from the English seed above rather than part of it,
    # because it doubles the catalogue and nobody should get it by having
    # left a default alone.
    #
    # Gated on there being none yet, so this costs a database question on
    # every start rather than a download.
    if [ "${SEED_JAPANESE:-false}" = "true" ]; then
      if python /seed/seed_cards_ja.py --check-empty; then
        echo "[seed] no Japanese cards — seeding them…"
        python /seed/seed_cards_ja.py --download \
          || echo "[seed] Japanese seed failed; run it by hand later"
      fi
    fi

    # After the seeds, inside the same subshell: on a first boot the cards
    # have to exist before there is anything to fingerprint.
    hash_art
  ) &
else
  # Seeding switched off does not mean the catalogue is empty — it means it
  # is managed by hand. Whatever is in it can still be fingerprinted.
  ( hash_art ) &
fi

# 0.0.0.0 is every IPv4 address on this container, which is what compose
# networking uses and what every self-hosted install wants.
#
# Some platform hosts route between services over IPv6 only — Railway is one —
# and there an IPv4-only listener resolves, accepts nothing, and looks exactly
# like a crashed API from the container next door. Setting BIND_HOST=:: listens
# on IPv6 (and, on Linux defaults, IPv4 with it). Left alone nothing changes.
exec uvicorn app.main:app --host "${BIND_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
