#!/bin/sh
# SYJ OpenTrade Logic - Docker entrypoint
# ==========================================
# data/hts_full.json is deliberately NOT committed to git (it's ~17,000+
# generated records, see .gitignore) -- so a fresh container needs to build
# it once on first startup, same as a fresh Termux checkout does. This
# requires the container to have real internet access on first run to reach
# the official USITC API. After that, it's cached in the mounted volume.

set -e

if [ ! -f "/app/data/hts_full.json" ]; then
    echo "[entrypoint] data/hts_full.json not found -- running the HTS importer (needs internet access)..."
    python3 scripts/import_hts_data.py
else
    echo "[entrypoint] data/hts_full.json already present, skipping import."
fi

exec uvicorn server_fastapi.main:app --host 0.0.0.0 --port 8000
