"""Database connection helper for the Food Traceback System.

Resolves PostgreSQL connection parameters in this order of precedence:

1. DATABASE_URL environment variable (a full libpq/psycopg2 DSN or URL).
2. DB_SECRET_ARN environment variable -> fetched from AWS Secrets Manager.
   The secret is expected to be JSON with keys: host, port, username,
   password, dbname (the shape RDS-managed master secrets use).
3. Individual PG* / DB_* environment variables, with sensible local defaults.

This keeps credentials out of source control: locally you export
DATABASE_URL (or PG* vars); in AWS the Lambda/ECS task reads DB_SECRET_ARN.
"""

from __future__ import annotations

import json
import os

import psycopg2


def _conn_params_from_secret(secret_arn: str) -> dict:
    """Fetch connection params from AWS Secrets Manager.

    boto3 is imported lazily so local runs that use DATABASE_URL do not
    require AWS credentials to be configured.
    """
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)
    raw = client.get_secret_value(SecretId=secret_arn)["SecretString"]
    secret = json.loads(raw)

    return {
        "host": secret["host"],
        "port": int(secret.get("port", 5432)),
        "user": secret["username"],
        "password": secret["password"],
        # RDS-managed secrets may omit dbname; fall back to env or default.
        "dbname": secret.get("dbname") or os.environ.get("DB_NAME", "foodtraceback"),
    }


def _conn_params_from_env() -> dict:
    return {
        "host": os.environ.get("DB_HOST", os.environ.get("PGHOST", "localhost")),
        "port": int(os.environ.get("DB_PORT", os.environ.get("PGPORT", "5432"))),
        "user": os.environ.get("DB_USER", os.environ.get("PGUSER", "postgres")),
        "password": os.environ.get("DB_PASSWORD", os.environ.get("PGPASSWORD", "")),
        "dbname": os.environ.get("DB_NAME", os.environ.get("PGDATABASE", "foodtraceback")),
    }


def get_connection():
    """Return a new psycopg2 connection using resolved parameters.

    Caller owns the connection lifecycle (commit/rollback/close).
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    secret_arn = os.environ.get("DB_SECRET_ARN")
    if secret_arn:
        return psycopg2.connect(**_conn_params_from_secret(secret_arn))

    return psycopg2.connect(**_conn_params_from_env())
