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


# ============================================================================
# Incident aggregation queries (Phase B)
#
# A recall points at a raw lot (via lot_code). To find everything downstream
# that is now suspect, we walk the lot graph FORWARD (raw lot -> blended
# descendants), then follow shipments to stores. This complements
# trace_origins() which walks backward (blended lot -> source farms).
# ============================================================================


def get_recall(recall_id: int) -> Optional[dict]:
    """Return a recall with its product name, or None if not found."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.product_id, p.name AS product_name,
                       r.lot_code, r.pathogen, r.status, r.created_at
                FROM recalls r
                LEFT JOIN products p ON p.id = r.product_id
                WHERE r.id = %s
                """,
                (recall_id,),
            )
            rows = _rows_as_dicts(cur)
            return rows[0] if rows else None
    finally:
        conn.close()


def trace_descendants(lot_id: int, max_depth: int = 50) -> list[int]:
    """Forward trace: the lot itself plus every lot blended from it.

    Walks lot_inputs forward (input_lot_id -> output_lot_id). For the recalled
    raw lot this returns the raw lot plus all downstream blended lots that must
    be considered contaminated. Depth guard prevents runaway/cyclic traversal.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id AS lot_id, 0 AS depth
                    FROM lots WHERE id = %s
                    UNION ALL
                    SELECT li.output_lot_id, d.depth + 1
                    FROM descendants d
                    JOIN lot_inputs li ON li.input_lot_id = d.lot_id
                    WHERE d.depth < %s
                )
                SELECT DISTINCT lot_id FROM descendants ORDER BY lot_id
                """,
                (lot_id, max_depth),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def affected_lot_ids_for_recall(recall: dict) -> list[int]:
    """Resolve a recall's lot_code to its lot, then forward-trace descendants.

    Returns the full set of affected lot ids (raw + blended). If the recall's
    lot_code does not resolve to a lot, returns an empty list.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM lots WHERE lot_code = %s", (recall["lot_code"],))
            row = cur.fetchone()
            if not row:
                return []
            root_lot_id = row[0]
    finally:
        conn.close()
    return trace_descendants(root_lot_id)


def all_stores() -> list[dict]:
    """Every store (for store_status and chain grouping)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, chain, city, state FROM stores ORDER BY id"
            )
            return _rows_as_dicts(cur)
    finally:
        conn.close()


def store_ids_that_received(lot_ids: list[int]) -> set[int]:
    """Distinct store ids that received a shipment of any affected lot."""
    if not lot_ids:
        return set()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT to_store_id
                FROM shipments
                WHERE to_store_id IS NOT NULL AND lot_id = ANY(%s)
                """,
                (lot_ids,),
            )
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def incident_stats(lot_ids: list[int]) -> dict:
    """Aggregate counts for the dashboard stat cards, scoped to affected lots."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stores")
            stores_tracked = cur.fetchone()[0]

            if not lot_ids:
                return {
                    "stores_tracked": stores_tracked,
                    "stores_received": 0,
                    "producers": 0,
                    "linked_cases": 0,
                    "lab_positive": 0,
                    "in_transit_stopped_packs": 0,
                }

            cur.execute(
                """
                SELECT COUNT(DISTINCT to_store_id)
                FROM shipments
                WHERE to_store_id IS NOT NULL AND lot_id = ANY(%s)
                """,
                (lot_ids,),
            )
            stores_received = cur.fetchone()[0]

            # Producers = distinct farms + facilities that originated affected lots.
            cur.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT farm_id AS id, 'farm' AS kind FROM lots
                    WHERE id = ANY(%s) AND farm_id IS NOT NULL
                    UNION
                    SELECT facility_id, 'facility' FROM lots
                    WHERE id = ANY(%s) AND facility_id IS NOT NULL
                ) producers
                """,
                (lot_ids, lot_ids),
            )
            producers = cur.fetchone()[0]

            # Linked cases = distinct cases exposed at stores that got affected lots.
            cur.execute(
                """
                SELECT COUNT(DISTINCT ce.case_id)
                FROM case_exposures ce
                JOIN shipments s
                  ON s.to_store_id = ce.store_id AND s.lot_id = ANY(%s)
                """,
                (lot_ids,),
            )
            linked_cases = cur.fetchone()[0]

            # Lab-positive results tied to affected lots.
            cur.execute(
                """
                SELECT COUNT(*) FROM lab_results
                WHERE status = 'positive' AND lot_id = ANY(%s)
                """,
                (lot_ids,),
            )
            lab_positive = cur.fetchone()[0]

            # In-transit packs of affected lots (flagged to stop).
            cur.execute(
                """
                SELECT COALESCE(SUM(quantity), 0)
                FROM shipments
                WHERE status = 'in_transit' AND lot_id = ANY(%s)
                """,
                (lot_ids,),
            )
            in_transit_stopped = cur.fetchone()[0]

            return {
                "stores_tracked": stores_tracked,
                "stores_received": stores_received,
                "producers": producers,
                "linked_cases": linked_cases,
                "lab_positive": lab_positive,
                "in_transit_stopped_packs": int(in_transit_stopped),
            }
    finally:
        conn.close()


def incident_suspects(lot_ids: list[int]) -> list[dict]:
    """Origin farms/facilities of affected lots, with lab-positive flag.

    This is the backward view: for every affected (incl. blended) lot, find the
    ultimate origin farms via the existing recursive origin trace, plus any
    facility that directly produced an affected blended lot.
    """
    if not lot_ids:
        return []

    # Collect farm origins by tracing each affected lot back to raw farms.
    farms: dict[int, dict] = {}
    for lid in lot_ids:
        for origin in trace_origins(lid):
            farms[origin["farm_id"]] = {
                "entity_type": "farm",
                "entity_id": origin["farm_id"],
                "name": origin["farm_name"],
                "city": origin["farm_city"],
            }

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Facilities that directly produced an affected lot.
            cur.execute(
                """
                SELECT DISTINCT fac.id, fac.name, fac.city, fac.type
                FROM lots l
                JOIN facilities fac ON fac.id = l.facility_id
                WHERE l.id = ANY(%s) AND l.facility_id IS NOT NULL
                """,
                (lot_ids,),
            )
            facilities = _rows_as_dicts(cur)

            # Which farms have a lab-positive lot?
            cur.execute(
                """
                SELECT DISTINCT l.farm_id
                FROM lab_results lr
                JOIN lots l ON l.id = lr.lot_id
                WHERE lr.status = 'positive' AND l.farm_id IS NOT NULL
                """
            )
            positive_farms = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    suspects: list[dict] = []
    for fid, f in sorted(farms.items()):
        f["lab_positive"] = fid in positive_farms
        suspects.append(f)
    for fac in facilities:
        suspects.append(
            {
                "entity_type": "facility",
                "entity_id": fac["id"],
                "name": fac["name"],
                "city": fac["city"],
                "facility_type": fac["type"],
                "lab_positive": False,
            }
        )
    return suspects
