#!/usr/bin/env sh
# Monthly card-data refresh: pulls the full pokemon-tcg-data dump and re-seeds
# (pure python — no git/curl needed in the container). Upserts by card id, so
# owned/wanted records are never touched.
#
# Schedule on TrueNAS (System Settings -> Advanced -> Cron Jobs), e.g.:
#   0 4 1 * *  docker exec getloot-api python /seed/seed_cards.py --download
set -e
python /seed/seed_cards.py --download
