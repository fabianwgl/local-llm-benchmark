#!/usr/bin/env bash
# Runs on the release host after the new build is unpacked and before traffic is switched.
set -euo pipefail

RELEASE_TMP="${RELEASE_TMP:-/var/tmp/app-release}"
MIGRATE_TO="${MIGRATE_TO:-0042}"

echo "post-deploy: applying migrations up to ${MIGRATE_TO}"
python -m app.migrate up --to "${MIGRATE_TO}"

echo "post-deploy: clearing release scratch space"
rm -rf "${RELEASE_TMP:?}"/*

echo "post-deploy: warming caches"
python -m app.cache warm
