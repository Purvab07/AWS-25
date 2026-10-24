"""ETL: load the Bay Area Food Traceback mock dataset into db/schema.sql.

The mock dataset (mock_data/food_safety_dataset/csv) was generated against an
earlier, simpler variant of the schema. This loader reads its CSVs and maps
them into the richer current schema (db/schema.sql) WITHOUT modifying that
schema. Where the target schema has columns the dataset lacks, values are
synthesized or defaulted; where the dataset splits data across extra tables,
those are joined back together here.

Mapping summary
---------------
Direct (same shape):   farms, stores, lots, lot_inputs, cases,
                       case_exposures, lab_results
Enriched:              facilities (+created_at), products (+unit/package_size/
                       attributes from product_specs)
Joined / remapped:     shipments  = shipments + shipment_state
                       supplier_inventory = supplier_offers
                       recalls    = events (+ earliest seed lot from event_lots)

Load order respects foreign keys. IDs are preserved from the source so FKs line
up; serial sequences are reset afterward so future inserts do not collide.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host:5432/dbname \\
        python scripts/load_seed.py [--data-dir PATH] [--truncate]

Connection resolution is handled by scripts/db.py.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from typing import Callable, Optional

# Allow running as a script from anywhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection  # noqa: E402

DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mock_data",
    "food_safety_dataset",
    "csv",
)

# Tables we populate, in FK-safe load order. Also the reverse-delete order
# when --truncate is used.
LOAD_ORDER = [
    "farms",
    "facilities",
    "stores",
    "products",
    "lots",
    "lot_inputs",
    "shipments",
    "supplier_inventory",
    "cases",
    "case_exposures",
    "lab_results",
    "recalls",
    "recall_shipment_flags",
]

# Tables whose SERIAL sequence must be re-synced after explicit-id inserts.
SERIAL_TABLES = [
    "farms",
    "facilities",
    "stores",
    "products",
    "lots",
    "shipments",
    "supplier_inventory",
    "cases",
    "case_exposures",
    "lab_results",
    "recalls",
]

# dataset shipment_state.status -> schema shipment_status enum
SHIPMENT_STATUS_MAP = {
    "planned": "scheduled",
    "in_transit": "in_transit",
    "delivered": "delivered",
    "held": "hold_review",
    "cancelled": "cancelled",
}


def _read_csv(data_dir: str, name: str) -> list[dict]:
    """Read a UTF-8 (BOM) CSV into a list of dict rows. Empty string -> None."""
    path = os.path.join(data_dir, f"{name}.csv")
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            rows.append({k: (v if v != "" else None) for k, v in row.items()})
        return rows


def _copy_rows(cur, table: str, columns: list[str], rows: list[list]) -> int:
    """Bulk-load rows into `table` using COPY for speed. Returns row count."""
    if not rows:
        return 0
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(["\\N" if v is None else v for v in r])
    buf.seek(0)
    col_list = ", ".join(columns)
    cur.copy_expert(
        f"COPY {table} ({col_list}) FROM STDIN WITH (FORMAT csv, NULL '\\N')",
        buf,
    )
    return len(rows)


# --- per-table builders: return (columns, rows) ready for COPY ---------------

def build_farms(data_dir):
    cols = ["id", "name", "city", "state", "latitude", "longitude", "created_at"]
    rows = [
        [r["id"], r["name"], r["city"], r["state"], r["latitude"], r["longitude"], r["created_at"]]
        for r in _read_csv(data_dir, "farms")
    ]
    return cols, rows


def build_facilities(data_dir):
    # Dataset facilities has no created_at; schema requires it (defaults now()).
    cols = ["id", "name", "type", "city", "state", "latitude", "longitude"]
    rows = [
        [r["id"], r["name"], r["type"], r["city"], r["state"], r["latitude"], r["longitude"]]
        for r in _read_csv(data_dir, "facilities")
    ]
    return cols, rows


def build_stores(data_dir):
    cols = ["id", "name", "chain", "address", "city", "state", "latitude", "longitude"]
    rows = [
        [r["id"], r["name"], r["chain"], r["address"], r["city"], r["state"],
         r["latitude"], r["longitude"]]
        for r in _read_csv(data_dir, "stores")
    ]
    return cols, rows


def build_products(data_dir):
    # Enrich minimal products with unit/package_size/attributes from product_specs.
    specs = {s["product_id"]: s for s in _read_csv(data_dir, "product_specs")}
    cols = ["id", "name", "category", "unit", "package_size", "attributes"]
    rows = []
    for p in _read_csv(data_dir, "products"):
        spec = specs.get(p["id"], {})
        unit = spec.get("quantity_unit")
        weight = spec.get("unit_weight_kg")
        package_size = f"{weight} kg" if weight else None
        # Preserve spec provenance in the JSONB attributes column.
        import json
        attrs = {}
        if spec.get("spec_code"):
            attrs["spec_code"] = spec["spec_code"]
        if spec.get("unit_cost_usd"):
            attrs["unit_cost_usd"] = spec["unit_cost_usd"]
        if spec.get("reference_retail_value_usd"):
            attrs["reference_retail_value_usd"] = spec["reference_retail_value_usd"]
        rows.append([p["id"], p["name"], p["category"], unit, package_size, json.dumps(attrs)])
    return cols, rows


def build_lots(data_dir):
    cols = ["id", "lot_code", "product_id", "farm_id", "facility_id", "production_date"]
    rows = [
        [r["id"], r["lot_code"], r["product_id"], r["farm_id"], r["facility_id"],
         r["production_date"]]
        for r in _read_csv(data_dir, "lots")
    ]
    return cols, rows


def build_lot_inputs(data_dir):
    cols = ["output_lot_id", "input_lot_id"]
    rows = [[r["output_lot_id"], r["input_lot_id"]] for r in _read_csv(data_dir, "lot_inputs")]
    return cols, rows


def build_shipments(data_dir):
    # Join shipments + shipment_state. ship_date is the fallback for shipped_at.
    state = {s["shipment_id"]: s for s in _read_csv(data_dir, "shipment_state")}
    cols = ["id", "lot_id", "from_farm_id", "from_facility_id", "to_facility_id",
            "to_store_id", "quantity", "status", "shipped_at", "delivered_at"]
    rows = []
    for sh in _read_csv(data_dir, "shipments"):
        st = state.get(sh["id"], {})
        raw_status = (st.get("status") or "scheduled")
        status = SHIPMENT_STATUS_MAP.get(raw_status, "scheduled")
        shipped_at = st.get("departure_at") or sh["ship_date"]
        delivered_at = st.get("received_at")
        rows.append([
            sh["id"], sh["lot_id"], sh["from_farm_id"], sh["from_facility_id"],
            sh["to_facility_id"], sh["to_store_id"], sh["quantity"],
            status, shipped_at, delivered_at,
        ])
    return cols, rows


def build_supplier_inventory(data_dir):
    # supplier_offers -> supplier_inventory. Lead time = processing + delivery.
    # is_available = TRUE only when the offer's safety_status is 'released'.
    cols = ["id", "farm_id", "facility_id", "product_id", "quantity_available",
            "unit_price", "estimated_lead_time_hours", "is_available"]
    rows = []
    for o in _read_csv(data_dir, "supplier_offers"):
        proc = float(o["processing_lead_hours"]) if o["processing_lead_hours"] else 0.0
        deliv = float(o["delivery_lead_hours"]) if o["delivery_lead_hours"] else 0.0
        lead = proc + deliv
        safety = (o.get("safety_status") or "").lower()
        approval = (o.get("approval_status") or "").lower()
        is_available = "TRUE" if (safety == "released" and approval != "blocked") else "FALSE"
        rows.append([
            o["id"], o["farm_id"], None, o["product_id"], o["available_units"],
            o["unit_cost_usd"], lead, is_available,
        ])
    return cols, rows


def build_cases(data_dir):
    cols = ["id", "onset_date", "city", "state", "latitude", "longitude",
            "pathogen", "raw_report", "created_at"]
    rows = [
        [r["id"], r["onset_date"], r["city"], r["state"], r["latitude"],
         r["longitude"], r["pathogen"], r["raw_report"], r["created_at"]]
        for r in _read_csv(data_dir, "cases")
    ]
    return cols, rows


def build_case_exposures(data_dir):
    cols = ["id", "case_id", "store_id", "product_id", "exposure_date"]
    rows = [
        [r["id"], r["case_id"], r["store_id"], r["product_id"], r["exposure_date"]]
        for r in _read_csv(data_dir, "case_exposures")
    ]
    return cols, rows


def build_lab_results(data_dir):
    cols = ["id", "lot_id", "case_id", "pathogen", "status", "tested_on"]
    rows = [
        [r["id"], r["lot_id"], r["case_id"], r["pathogen"], r["status"], r["tested_on"]]
        for r in _read_csv(data_dir, "lab_results")
    ]
    return cols, rows


def build_recalls(data_dir):
    # events -> recalls. lot_code = code of the earliest (seed) lot for the event.
    lots = {lt["id"]: lt for lt in _read_csv(data_dir, "lots")}
    event_lots = _read_csv(data_dir, "event_lots")
    seed_lot_for_event: dict = {}
    for el in event_lots:
        if el["scope_type"] == "seed" and el["event_id"] not in seed_lot_for_event:
            lot = lots.get(el["lot_id"])
            if lot:
                seed_lot_for_event[el["event_id"]] = lot["lot_code"]

    cols = ["id", "product_id", "lot_code", "pathogen", "reason", "source",
            "raw_notice", "status", "created_at"]
    rows = []
    for e in _read_csv(data_dir, "events"):
        # events.current_status is free-text; map resolved-ish states to 'resolved'.
        cur = (e.get("current_status") or "").lower()
        status = "resolved" if ("closed" in cur or "resolved" in cur or "released" in cur) else "active"
        rows.append([
            e["id"], e["product_id"], seed_lot_for_event.get(e["id"]),
            e["suspected_pathogen"], e["title"], "synthetic_dataset_event",
            e["title"], status, e["reported_at"],
        ])
    return cols, rows


BUILDERS: dict[str, Callable[[str], tuple]] = {
    "farms": build_farms,
    "facilities": build_facilities,
    "stores": build_stores,
    "products": build_products,
    "lots": build_lots,
    "lot_inputs": build_lot_inputs,
    "shipments": build_shipments,
    "supplier_inventory": build_supplier_inventory,
    "cases": build_cases,
    "case_exposures": build_case_exposures,
    "lab_results": build_lab_results,
    "recalls": build_recalls,
    # recall_shipment_flags has no source data; left empty (audit trail is
    # produced at runtime by the recall workflow).
}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Load mock dataset into the schema.")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                        help="Directory containing the dataset CSV files.")
    parser.add_argument("--truncate", action="store_true",
                        help="Delete existing rows from target tables first.")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.data_dir):
        print(f"ERROR: data dir not found: {args.data_dir}", file=sys.stderr)
        return 2

    conn = get_connection()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if args.truncate:
                for table in reversed(LOAD_ORDER):
                    cur.execute(f"DELETE FROM {table}")
                print("Cleared existing rows from target tables.")

            total = 0
            for table in LOAD_ORDER:
                builder = BUILDERS.get(table)
                if builder is None:
                    continue
                columns, rows = builder(args.data_dir)
                n = _copy_rows(cur, table, columns, rows)
                total += n
                print(f"  loaded {n:>5} -> {table}")

            # Re-sync SERIAL sequences to MAX(id) so future inserts don't clash.
            for table in SERIAL_TABLES:
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM {t}), 1), "
                    "(SELECT COUNT(*) FROM {t}) > 0)".format(t=table),
                    (table,),
                )

        conn.commit()
        print(f"Done. {total} rows loaded across {len(BUILDERS)} tables.")
        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"ERROR: load failed, rolled back. {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
