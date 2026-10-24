"""FastAPI layer for the Food Traceback System — Phase A.

Two live endpoints backed by the real RDS database and the existing Bedrock
replacement engine:

  GET  /api/traceback/{lot_id}   -> recursive farm-origin traceback of a lot
  POST /api/replacements         -> DB-sourced candidates -> Bedrock ranking

Run locally (from repo root, with DATABASE_URL and AWS creds in the env):

    .venv/bin/uvicorn backend.api.app:app --reload --port 8000

A static-friendly CORS policy is enabled so the incident-console frontend
(served on :8099) can call this API from the browser.
"""

from __future__ import annotations

import decimal
import os
import sys
from datetime import date, datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- make sibling backend packages + scripts importable ---------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.api import queries  # noqa: E402
from backend.ai_automation.replacement_engine import find_replacements  # noqa: E402
from backend.ai_automation.replacement_ranker import rank_replacements  # noqa: E402

app = FastAPI(title="Food Traceback API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon/demo; tighten for anything real
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- simple in-memory TTL cache --------------------------------------------
# The incident snapshot is effectively static between page loads but costs a
# few seconds to compute (many sequential round-trips to a remote RDS). Caching
# it makes every load after the first near-instant. TTL keeps it fresh enough
# that DB changes still show up within a short window.
import time as _time  # noqa: E402

_CACHE_TTL_SECONDS = 60
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and (_time.time() - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_put(key: str, value: Any):
    _cache[key] = (_time.time(), value)


def _jsonable(value: Any) -> Any:
    """Convert DB types (Decimal, date/datetime) into JSON-friendly values."""
    if isinstance(value, decimal.Decimal):
        # Keep integers as int, else float.
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


@app.get("/health")
def health() -> dict:
    """Liveness + DB connectivity check."""
    try:
        lot = queries.get_lot(1)
        return {"status": "ok", "db": "reachable", "sample_lot_found": lot is not None}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"db unreachable: {exc}")


@app.get("/api/traceback/{lot_id}")
def traceback(lot_id: int) -> dict:
    """Trace a lot back to its ultimate farm origins (recursive lot_inputs)."""
    lot = queries.get_lot(lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail=f"lot {lot_id} not found")

    origins = queries.trace_origins(lot_id)
    stores = queries.stores_that_received(lot_id)

    return _jsonable(
        {
            "lot": lot,
            "origin_farms": origins,
            "origin_farm_count": len({o["farm_id"] for o in origins}),
            "stores_received": stores,
            "store_count": len(stores),
        }
    )


class ReplacementRequest(BaseModel):
    recalled_product_id: int
    quantity_needed: int = 1


@app.post("/api/replacements")
def replacements(req: ReplacementRequest) -> dict:
    """Recommend replacement suppliers for a recalled product.

    In a food recall, the ideal replacement is the SAME product from a
    different, available supplier. The Bedrock product-matcher, however, is
    designed to judge whether a *different* product is a compatible substitute,
    and it (correctly, by its own logic) rejects the recalled product itself as
    a "replacement". So we split candidates:

      * same product id as the recalled product -> auto-matched here (identity
        is certain; a clean supplier's stock of the same product is the best
        replacement). No Bedrock call needed.
      * different product id -> sent to the existing Bedrock engine to assess
        cross-product substitution.

    Both groups are ranked together using the shared ranker so ordering stays
    consistent. The teammate-owned backend/ai_automation modules are left
    unchanged.
    """
    recalled = queries.get_product(req.recalled_product_id)
    if recalled is None:
        raise HTTPException(
            status_code=404, detail=f"product {req.recalled_product_id} not found"
        )

    candidates = queries.candidate_suppliers(include_product_id=None)
    candidates = [c for c in candidates]  # all available inventory
    if not candidates:
        return _jsonable(
            {
                "recalled_product": recalled,
                "recommended": None,
                "alternatives": [],
                "message": "No available supplier inventory to evaluate.",
            }
        )

    same_product = [c for c in candidates if c["product_id"] == recalled["id"]]
    other_product = [c for c in candidates if c["product_id"] != recalled["id"]]

    evaluated: list[dict] = []

    # Same product, different supplier -> automatic, certain match.
    for c in same_product:
        c = c.copy()
        c["is_match"] = True
        c["match_reason"] = "Same product from an alternate, available supplier."
        evaluated.append(c)

    # Different products -> let Bedrock judge substitution compatibility.
    if other_product:
        try:
            result = find_replacements(recalled, other_product, req.quantity_needed)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502, detail=f"replacement engine failed: {exc}"
            )
        # find_replacements already ranked/filtered the different-product set;
        # fold its qualifying rows back in for a combined ranking.
        for row in [result.get("recommended")] + result.get("alternatives", []):
            if row:
                evaluated.append(row)

    ranked = rank_replacements(evaluated, req.quantity_needed)

    if not ranked:
        return _jsonable(
            {
                "recalled_product": recalled,
                "recommended": None,
                "alternatives": [],
                "message": "No eligible replacement supplier found.",
            }
        )

    return _jsonable(
        {
            "recalled_product": recalled,
            "recommended": ranked[0],
            "alternatives": ranked[1:3],
            "message": "Replacement suppliers found.",
        }
    )


@app.get("/api/incident/{recall_id}")
def incident(recall_id: int) -> dict:
    """Live incident snapshot for the dashboard.

    Returns only the data-backed fields; the frontend merges these over its
    static layout/copy. Core field groups: recall, incident, stats,
    store_status, chains, suspects. (retail/facilities tables are a
    fast-follow.)

    Cached in-memory with a short TTL so repeated page loads are instant.
    """
    cache_key = f"incident:{recall_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    recall = queries.get_recall(recall_id)
    if recall is None:
        raise HTTPException(status_code=404, detail=f"recall {recall_id} not found")

    lot_ids = queries.affected_lot_ids_for_recall(recall)
    received = queries.store_ids_that_received(lot_ids)
    stores = queries.all_stores()

    # incident header fields (title/summary copy composed on the frontend)
    created = recall.get("created_at")
    incident_block = {
        "id": f"DEMO-E{recall['id']:02d}",
        "activeSince": created.strftime("%H:%M") if created else None,
        "pathogen": recall.get("pathogen"),
        "product_name": recall.get("product_name"),
    }

    # per-store status WITH coordinates (for the real map)
    store_status = [
        {
            "id": s["id"],
            "name": s["name"],
            "chain": s["chain"],
            "city": s["city"],
            "lat": s["latitude"],
            "lng": s["longitude"],
            "received": s["id"] in received,
        }
        for s in stores
    ]

    # chains: stores grouped by chain
    chains_map: dict[str, list] = {}
    for s in stores:
        chains_map.setdefault(s["chain"] or "Unknown", []).append(
            {"id": s["id"], "city": s["city"]}
        )
    chains = [{"name": name, "stores": members} for name, members in chains_map.items()]

    suspects = queries.incident_suspects(lot_ids)

    payload = _jsonable(
        {
            "recall": recall,
            "incident": incident_block,
            "affected_lot_ids": lot_ids,
            "stats": queries.incident_stats(lot_ids),
            "store_status": store_status,
            "chains": chains,
            "suspects": suspects,
            "producers": queries.producer_coords(suspects),
            "cases": [
                {
                    "id": c["id"],
                    "city": c["city"],
                    "lat": c["latitude"],
                    "lng": c["longitude"],
                    "pathogen": c["pathogen"],
                }
                for c in queries.incident_cases(lot_ids)
            ],
        }
    )
    _cache_put(cache_key, payload)
    return payload
