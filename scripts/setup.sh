#!/usr/bin/env bash
# One-time setup: create the Python venv and install dependencies.
# Safe to re-run (idempotent).
#
#   ./scripts/setup.sh
#
# After this, configure credentials (.env from .env.example) and run
# ./scripts/start.sh

set -euo pipefail

# Resolve repo root (this script lives in scripts/).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Food Traceback setup"

# --- prerequisite checks ------------------------------------------------
missing=0
check() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "  MISSING: $1 — $2"
    missing=1
  else
    echo "  ok: $1 ($(command -v "$1"))"
  fi
}
echo "-- checking prerequisites --"
check python3 "install Python 3.10+ (3.9 works but is deprecated by boto3)"
check node    "install Node.js (for the frontend static server)"
check psql    "optional: install the postgresql client for manual DB checks"

if [ "$missing" -eq 1 ]; then
  echo "Install the missing tools above, then re-run ./scripts/setup.sh"
  exit 1
fi

# --- virtualenv + deps --------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "-- creating virtualenv (.venv) --"
  python3 -m venv .venv
else
  echo "-- reusing existing .venv --"
fi

echo "-- installing dependencies --"
./.venv/bin/pip install -q --upgrade pip
# The API requirements include scripts/requirements.txt via -r, so this one
# command installs everything (base ETL deps + API deps) with no duplication.
./.venv/bin/pip install -q -r backend/api/requirements.txt

echo "-- dependencies installed --"

# --- env file ------------------------------------------------------------
# Create .env from the template ONLY if it does not already exist, so we never
# overwrite credentials a user has already filled in.
if [ -f ".env" ]; then
  echo "-- .env already exists; leaving it untouched --"
else
  cp .env.example .env
  echo
  echo "Created .env from the template. Now fill in the real values:"
  echo "    \$EDITOR .env"
  echo "(DB password: ask a teammate. AWS creds: from the Workshop portal.)"
  echo "Do NOT re-copy .env.example over .env afterwards — it will overwrite them."
fi

echo
echo "Setup complete. Start everything with:  ./scripts/start.sh"
