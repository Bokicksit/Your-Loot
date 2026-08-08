#!/usr/bin/env sh
# Card-data refresh: pulls the full pokemon-tcg-data dump and re-seeds (pure
# python — no git/curl needed in the container). Upserts by card id, so owned
# copies, wanted flags, binder picks, grades and self-set images all survive.
#
# Schedule on TrueNAS (System Settings -> Advanced -> Cron Jobs, run as root).
# Weekly keeps up with new sets and promo additions:
#   0 4 * * 0  docker exec yourloot-api python /seed/seed_cards.py --download
set -e
python /seed/seed_cards.py --download
