#!/usr/bin/env sh
# Monthly card-data refresh STUB. Pulls the full pokemon-tcg-data dump and
# re-seeds (upserts, so owned/wanted records are untouched).
#
# Schedule it on TrueNAS (System Settings -> Advanced -> Cron Jobs), e.g.:
#   0 4 1 * *  docker exec getloot-api sh /seed/refresh_cards.sh
#
# NOTE: python:3.12-slim has no git — when enabling this, add
#   RUN apt-get update && apt-get install -y --no-install-recommends git
# to api/Dockerfile (or swap the clone for a tarball download via curl).
set -e

echo "Fetching pokemon-tcg-data..."
rm -rf /tmp/ptcg
# TODO(phase 2): pin a release tag instead of default branch; the full dump is
# ~every English set — expect the first run to take a few minutes.
git clone --depth 1 https://github.com/PokemonTCG/pokemon-tcg-data /tmp/ptcg

python /seed/seed_cards.py --cards-dir /tmp/ptcg/cards/en --sets-file /tmp/ptcg/sets/en.json

rm -rf /tmp/ptcg
echo "Refresh complete."
