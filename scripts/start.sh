#!/usr/bin/env bash
# Start the Food Traceback demo: API (uvicorn :8000) + frontend (:8099).
#
#   ./scripts/start.sh
#
# Loads .env if present. Requires DATABASE_URL and AWS credentials to be set
# (see .env.example). Run ./scripts/setup.sh first if you haven't.
#
# The API runs in the background; the frontend runs in the foreground. Press
# Ctrl-C to stop both.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API_PORT=8000
FE_PORT=8099

# --- load .env if present ----------------------------------------------
if [ -f ".env" ]; then
  echo "-- loading .env --"
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# --- preflight checks ---------------------------------------------------
fail() { echo "ERROR: $1" >&2; exit 1; }

[ -d ".venv" ] || fail "no .venv found. Run ./scripts/setup.sh first."

if [ -z "${DATABASE_URL:-}" ]; then
  fail "DATABASE_URL is not set. Copy .env.example to .env and fill it in, \
or export DATABASE_URL in your shell."
fi

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -z "${AWS_PROFILE:-}" ]; then
  echo "WARNING: no AWS credentials detected (AWS_ACCESS_KEY_ID / AWS_PROFILE)."
  echo "         The traceback + incident endpoints work without them, but"
  echo "         /api/replacements calls Bedrock and will fail. Paste your"
  echo "         Workshop 'export AWS_...' block if you need replacements."
fi

# --- DB connectivity check (detect the IP-allowlist gotcha early) -------
echo "-- checking database connectivity --"
if ! ./.venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, "scripts")
try:
    from db import get_connection
    c = get_connection(); c.close()
    print("  db: reachable")
except Exception as exc:
    print(f"  db: UNREACHABLE — {exc}", file=sys.stderr)
    sys.exit(1)
PY
then
  cat >&2 <<'MSG'

Could not reach the database. The most common cause is that your machine's
public IP is not allow-listed on the RDS security group (connections from
other IPs time out). Add your current IP with:

  NEW_IP=$(curl -s https://checkip.amazonaws.com)
  SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=ft-rds-sg" --query 'SecurityGroups[0].GroupId' --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 5432 --cidr "$NEW_IP/32"

(Needs your AWS credentials loaded.) See docs/aws-setup.md for details.
MSG
  exit 1
fi

# --- start servers ------------------------------------------------------
# API in the background; frontend in the foreground. Ctrl-C stops both.
echo "-- starting API on :$API_PORT --"
./.venv/bin/uvicorn backend.api.app:app --port "$API_PORT" &
API_PID=$!

cleanup() {
  echo
  echo "-- shutting down --"
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the API a moment, then confirm it is up.
sleep 2
if curl -s -m 5 "http://localhost:$API_PORT/health" >/dev/null 2>&1; then
  echo "  api: http://localhost:$API_PORT (healthy)"
else
  echo "  api: started (health check pending) — see logs above"
fi

echo "-- starting frontend on :$FE_PORT (Ctrl-C to stop both) --"
echo "   open http://localhost:$FE_PORT in your browser"
cd incident-console/incident-console
exec node serve.js
