"""Read queries against the Food Traceback database.

These are the live data-access functions the API serves. They use the shared
connection helper in scripts/db.py (same resolution: DATABASE_URL, then
DB_SECRET_ARN via Secrets Manager, then PG*/DB_* env vars).

Every function opens a connection, reads, and closes it. For a hackathon-scale
API this is simple and correct; a connection pool can be added later if needed.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

# Make scripts/db.py importable regardless of where uvicorn is launched from.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPTS = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from db import get_connection  # noqa: E402


def _rows_as_dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_lot(lot_id: int) -> Optional[dict]:
    """Return a single lot with its product name, or None if not found."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id, l.lot_code, l.product_id, p.name AS product_name,
                       l.farm_id, l.facility_id, l.production_date
                FROM lots l
                JOIN products p ON p.id = l.product_id
                WHERE l.id = %s
                """,
                (lot_id,),
            )
            rows = _rows_as_dicts(cur)
            return rows[0] if rows else None
    finally:
        conn.close()


def trace_origins(lot_id: int, max_depth: int = 50) -> list[dict]:
    """Recursively resolve a lot to its ultimate raw (farm) origin lots.

    Walks lot_inputs backward from the given lot. Returns the distinct origin
    lots bound to a farm, with farm details. This is the core traceback: for a
    blended lot it reaches every contributing farm. The depth guard prevents
    runaway/cyclic traversal.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE origin_trace AS (
                    SELECT id AS lot_id, 0 AS depth
                    FROM lots WHERE id = %s
                    UNION ALL
                    SELECT li.input_lot_id, ot.depth + 1
                    FROM origin_trace ot
                    JOIN lot_inputs li ON li.output_lot_id = ot.lot_id
                    WHERE ot.depth < %s
                )
                SELECT DISTINCT
                       l.id   AS origin_lot_id,
                       l.lot_code,
                       l.product_id,
                       f.id   AS farm_id,
                       f.name AS farm_name,
                       f.city AS farm_city,
                       f.state AS farm_state,
                       f.latitude,
                       f.longitude
                FROM origin_trace ot
                JOIN lots l  ON l.id = ot.lot_id
                JOIN farms f ON f.id = l.farm_id
                WHERE l.farm_id IS NOT NULL
                ORDER BY origin_lot_id
                """,
                (lot_id, max_depth),
            )
            return _rows_as_dicts(cur)
    finally:
        conn.close()


def stores_that_received(lot_id: int) -> list[dict]:
    """Stores that directly received shipments of this lot."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT s.id, s.name, s.chain, s.city, s.state,
                       s.latitude, s.longitude
                FROM shipments sh
                JOIN stores s ON s.id = sh.to_store_id
                WHERE sh.lot_id = %s AND sh.to_store_id IS NOT NULL
                ORDER BY s.id
                """,
                (lot_id,),
            )
            return _rows_as_dicts(cur)
    finally:
        conn.close()


def get_product(product_id: int) -> Optional[dict]:
    """Return a product row for use as the recalled product in matching."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, category, description, variety, package_size, unit
                FROM products WHERE id = %s
                """,
                (product_id,),
            )
            rows = _rows_as_dicts(cur)
            return rows[0] if rows else None
    finally:
        conn.close()


def candidate_suppliers(include_product_id: Optional[int] = None) -> list[dict]:
    """Available supplier inventory, shaped for the replacement engine.

    Produces the candidate dict fields find_replacements() expects:
    product_id, product_name, category, description, variety, package_size,
    supplier, quantity_available, unit_price, estimated_lead_time_hours,
    is_available. Also includes inventory_id (supplier_inventory.id) so the
    caller can distinguish multiple suppliers offering the same product.
    (distance_miles is omitted; the ranker treats missing distance as neutral.)

    In a food recall the realistic replacement is the SAME product from a
    different, available supplier. When include_product_id is given, candidates
    are scoped to that product's available inventory. When None, all available
    inventory is returned.

    Only currently-available inventory with stock on hand is returned.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    si.id          AS inventory_id,
                    si.product_id,
                    p.name        AS product_name,
                    p.category,
                    p.description,
                    p.variety,
                    p.package_size,
                    COALESCE(f.name, fac.name) AS supplier,
                    si.quantity_available,
                    si.unit_price,
                    si.estimated_lead_time_hours,
                    si.is_available
                FROM supplier_inventory si
                JOIN products p ON p.id = si.product_id
                LEFT JOIN farms f       ON f.id = si.farm_id
                LEFT JOIN facilities fac ON fac.id = si.facility_id
                WHERE si.is_available = TRUE
                  AND si.quantity_available > 0
                  AND (%s::int IS NULL OR si.product_id = %s::int)
                ORDER BY si.estimated_lead_time_hours ASC NULLS LAST,
                         si.quantity_available DESC
                """,
                (include_product_id, include_product_id),
            )
            return _rows_as_dicts(cur)
    finally:
        conn.close()
