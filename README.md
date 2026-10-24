# AWS-25 — Food Traceback & Recall Console

A food supply-chain traceback and recall-response system. It traces contaminated
lots backward to source farms and forward to affected stores, recommends
replacement suppliers using AWS Bedrock, and visualizes an active incident on a
live map.

**Stack:** PostgreSQL on AWS RDS · Python/FastAPI backend · AWS Bedrock
(Nova 2 Lite) · vanilla-JS + Leaflet frontend (the "incident console").

## Architecture at a glance

```
incident-console/ (browser)  ->  FastAPI (backend/api, :8000)  ->  RDS Postgres
                                           |
                                           +-------------------->  AWS Bedrock
```

- `db/schema.sql` — the database schema (idempotent; safe to re-run).
- `scripts/` — DB connection helper, CSV seed loader, and the setup/start scripts.
- `backend/api/` — FastAPI app with traceback, replacement, and incident endpoints.
- `backend/ai_automation/` — Bedrock-based product matching & replacement ranking.
- `incident-console/incident-console/` — the dashboard (served on :8099).
- `docs/aws-setup.md` — AWS/RDS details, Bedrock model, and teardown.

## Prerequisites

- **Python 3.10+** (3.9 works but is deprecated by boto3)
- **Node.js** (runs the frontend static server)
- **psql** (optional, for manual DB checks)
- Access to the shared **RDS database password** (ask a teammate)
- Your own **AWS credentials** from the Workshop portal (for Bedrock)

## Setup (first time)

From the repo root:

```bash
./scripts/setup.sh
```

This checks prerequisites, creates a Python virtualenv (`.venv`), installs
dependencies, and creates a `.env` file from `.env.example` **if one does not
already exist**.

> Do **not** run `cp .env.example .env` yourself after editing `.env` — it will
> overwrite your credentials. `setup.sh` only creates `.env` when it's missing.

Then open `.env` and fill in the real values (see **Credentials** below).

## Credentials

Credentials live only in your local `.env`, which is gitignored and never
committed. `.env.example` is the committed template with placeholders.

Fill in `.env`:

- **`DATABASE_URL`** — the RDS connection string. Replace
  `REPLACE_WITH_DB_PASSWORD` with the real master password (ask a teammate).
  The endpoint/host is already filled in.
- **AWS credentials** (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`) — paste your **own** short-lived block from the Workshop
  portal's "Get AWS CLI credentials" link. These expire; re-paste when they do.
  Needed only for the Bedrock-backed `/api/replacements` endpoint.

If your DB password contains shell-special characters (`$`, backticks, `#`,
spaces), prefer the separate variables instead of embedding it in the URL
(remove the `DATABASE_URL` line and use these, quoting the password):

```
DB_HOST=food-traceback-db.cqgkvonwoxhz.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_USER=ftadmin
DB_NAME=foodtraceback
DB_PASSWORD='your-exact-password'
```

### One-time network step: allow-list your IP

RDS only accepts connections from specific public IPs. If `start.sh` reports a
network/timeout error, add your current IP (requires your AWS creds loaded):

```bash
NEW_IP=$(curl -s https://checkip.amazonaws.com)
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=ft-rds-sg" --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 5432 --cidr "$NEW_IP/32"
```

Re-run this whenever you change networks. See `docs/aws-setup.md` for details.

## Run

```bash
./scripts/start.sh
```

This loads `.env`, verifies the database is reachable, then starts:

- the **API** on http://localhost:8000 (background)
- the **frontend** on http://localhost:8099 (foreground)

Open **http://localhost:8099** in your browser. Press **Ctrl-C** to stop both.

The dashboard fetches live data from the API; if the API is unavailable it
falls back to static demo data, so it still renders.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | DB connectivity check |
| GET | `/api/traceback/{lot_id}` | Trace a lot back to origin farms + receiving stores |
| POST | `/api/replacements` | Recommend replacement suppliers (Bedrock + inventory) |
| GET | `/api/incident/{recall_id}` | Live incident snapshot for the dashboard |

## Troubleshooting

- **`password authentication failed for user "ftadmin"`** — wrong DB password
  in `.env`. Fix it (common cause: a typo, or `.env` was overwritten by a stray
  `cp .env.example .env`).
- **Connection times out / `no .venv found`** — run `./scripts/setup.sh` first,
  and if it still times out, allow-list your IP (above).
- **`/api/replacements` fails but others work** — AWS credentials are missing or
  expired; re-paste your Workshop `export AWS_...` block into `.env` (or the
  shell) and restart.
- **Map tiles don't load** — the map needs internet (OpenStreetMap tiles).
  Markers still plot without tiles.

## Reseeding the database

The schema and seed data are already loaded on RDS. To re-apply from scratch
(e.g. a fresh database), see `docs/aws-setup.md` for the `psql -f db/schema.sql`
and `scripts/load_seed.py` steps.
