# AWS Setup Notes — Food Traceback System

Reference for the deployed infrastructure and how to reconnect/reload. This is
a temporary **AWS Workshop Studio** account (`WSParticipantRole`), so everything
here is ephemeral and gets wiped when the workshop ends. The portable assets are
`db/schema.sql` and `scripts/load_seed.py` — they run against any Postgres.

> Never commit credentials. The DB password and portal credentials live only in
> your shell session. `.env`, `*.pgpass`, and `.venv/` are gitignored.

## Account / region

- Account: `235669141645`
- Role: `WSParticipantRole/Participant`
- Region: `us-east-1`
- Default VPC: `vpc-0cfc0cf03f3d09201` (6 public subnets)

Credentials are short-lived. When CLI commands start failing with an
expired-token error, re-copy the `export` block from the portal's
"Get AWS CLI credentials" link into the same terminal.

## RDS PostgreSQL

- Identifier: `food-traceback-db`
- Endpoint: `food-traceback-db.cqgkvonwoxhz.us-east-1.rds.amazonaws.com`
- Engine: PostgreSQL 16, `db.t4g.micro`, 20 GB gp3, single-AZ, public
- DB name: `foodtraceback`, master user: `ftadmin`
- Security group: `ft-rds-sg` — inbound 5432 restricted to specific IPs only

### Reconnecting from a new network (IP changed)

RDS access is scoped to your network's **public IP**. When you move networks
(e.g. home vs. venue), add the new IP to the security group:

```zsh
NEW_IP=$(curl -s https://checkip.amazonaws.com)
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=ft-rds-sg" --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 5432 --cidr "$NEW_IP/32"
```

A connection that hangs ~30s then times out is almost always a stale IP rule.

## Load / reload the database

Set the password and connection string in your shell (zsh):

```zsh
read -s "DB_PASSWORD?RDS master password: "; echo
export DATABASE_URL="postgresql://ftadmin:$DB_PASSWORD@food-traceback-db.cqgkvonwoxhz.us-east-1.rds.amazonaws.com:5432/foodtraceback"
```

Apply schema (idempotent — the DROP teardown makes it re-runnable):

```zsh
PGPASSWORD="$DB_PASSWORD" psql -h food-traceback-db.cqgkvonwoxhz.us-east-1.rds.amazonaws.com -p 5432 -U ftadmin -d foodtraceback -v ON_ERROR_STOP=1 -f db/schema.sql
```

Seed (maps the mock dataset into the schema). `--truncate` reloads without
recreating the schema:

```zsh
.venv/bin/python scripts/load_seed.py
```

Expected: 393 rows across 12 tables. Verify with row counts (farms=6,
shipments=249, recalls=3) and the recursive traceback of lot 3, which should
return both DEMO Farm A and DEMO Farm B.

## Bedrock

- Model: `us.amazon.nova-2-lite-v1:0`, region `us-east-1`. Verified working via
  the Converse API. Region and model id are hardcoded in
  `backend/ai_automation/bedrock_client.py`.
- Auth uses ambient boto3 credentials, so the backend must run in a shell that
  has the Workshop `export AWS_...` block loaded.

## Backend API (Phase A)

FastAPI layer in `backend/api/` exposing two live endpoints backed by RDS +
Bedrock. Run from the repo root in a shell that has BOTH `DATABASE_URL` and the
AWS `export` block loaded:

```zsh
.venv/bin/pip install -r backend/api/requirements.txt   # first time only
.venv/bin/uvicorn backend.api.app:app --reload --port 8000
```

Endpoints:

- `GET /health` — DB connectivity check.
- `GET /api/traceback/{lot_id}` — recursive farm-origin traceback + receiving
  stores. (Lot 3 returns 2 origin farms and 18 stores.)
- `POST /api/replacements` — body `{"recalled_product_id": int, "quantity_needed": int}`.
  Returns a ranked replacement supplier. Same-product/different-supplier
  candidates are auto-matched in the API layer (Bedrock rejects the recalled
  product as its own replacement); genuinely different products go to the
  Bedrock engine.

## Teardown (when done, to stop any billing)

```zsh
aws rds delete-db-instance --db-instance-identifier food-traceback-db --skip-final-snapshot --delete-automated-backups
# after the instance is gone:
aws ec2 delete-security-group --group-name ft-rds-sg
```
