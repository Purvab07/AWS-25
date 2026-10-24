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
import threading

import psycopg2
from psycopg2 import pool as _pg_pool


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


def _connect_kwargs():
    """Resolve how to connect: a DSN string or a params dict.

    Returns (args, kwargs) suitable for psycopg2 connect calls.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return (database_url,), {}

    secret_arn = os.environ.get("DB_SECRET_ARN")
    if secret_arn:
        return (), _conn_params_from_secret(secret_arn)

    return (), _conn_params_from_env()


# --- connection pool --------------------------------------------------------
# Opening a fresh connection to a remote RDS instance costs ~0.5s (TCP + TLS +
# auth). The API opens many connections per request, so without pooling a
# single page load spent several seconds just on handshakes. A small pool keeps
# connections warm and reused across requests.

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """Lazily build (once) and return the shared connection pool."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:  # double-checked under the lock
                args, kwargs = _connect_kwargs()
                _pool = _pg_pool.ThreadedConnectionPool(1, 10, *args, **kwargs)
    return _pool


class _PooledConnection:
    """Proxy over a pooled psycopg2 connection.

    Delegates everything to the real connection, except close(): that returns
    the connection to the pool instead of tearing down the socket. This lets
    existing callers keep their `conn = get_connection(); ...; conn.close()`
    pattern unchanged while actually reusing connections.
    """

    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._returned = False

    def close(self):
        if self._returned:
            return
        self._returned = True
        try:
            if not self._conn.closed:
                # Roll back any open transaction so a reused connection never
                # carries leftover state to the next caller.
                self._conn.rollback()
            self._pool.putconn(self._conn)
        except Exception:
            # If returning cleanly fails, drop the connection from the pool.
            try:
                self._pool.putconn(self._conn, close=True)
            except Exception:
                pass

    def __getattr__(self, name):
        # Delegate attribute access (cursor, commit, rollback, ...) to the conn.
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)


def get_connection():
    """Return a pooled database connection.

    Callers keep the same lifecycle (commit/rollback, then close()); close()
    returns the connection to the pool rather than closing the socket.

    Dead connections (e.g. idle-dropped by RDS) are detected and replaced so a
    stale pooled connection never surfaces to the caller.
    """
    pool = _get_pool()
    conn = pool.getconn()

    # Cheap liveness check only: if psycopg2 already knows the socket is closed
    # (e.g. RDS dropped an idle connection), swap it for a fresh one. We do NOT
    # issue a round-trip query here — that would add remote latency to every
    # checkout and defeat the pool. A genuinely dead-but-"open" connection will
    # surface an error on first use, which callers already handle.
    if conn.closed:
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool.getconn()

    return _PooledConnection(pool, conn)
