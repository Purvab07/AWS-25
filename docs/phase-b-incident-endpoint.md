# Phase B — Incident Aggregation Endpoint Design

Goal: feed the `incident-console` dashboard with **live** data from RDS instead
of the hardcoded `DATA` object in `data.js`, without discarding the hand-tuned
map layout and editorial copy the frontend already contains.

## Approach: hybrid merge, not full replacement

The frontend's `DATA` object mixes three kinds of fields:

1. **Live data** — counts, store lists, suspect origins, chain aggregates.
   These come from the database.
2. **Layout constants** — map `x`/`y` percentages, filter labels, highway
   labels. Pure visual; no DB source.
3. **Editorial copy** — badge wording, bullet explanations, timeline narrative,
   disclaimer footnote. Human-authored.

So the plan is:

- A new endpoint `GET /api/incident/{recall_id}` returns ONLY the live fields.
- `data.js` is trimmed to keep layout + copy (and acts as the fallback shape).
- `app.js` fetches the endpoint, deep-merges the live fields over the static
  `DATA`, then calls `main()`.

This keeps the polished schematic map and copy while making every number real.

## Data path (verified against the seeded DB)

Recall 1 = lot_code `DEMO-P1-RAW-A` = raw **lot 1** (Farm A, product 1).
Lot 1 is blended into **lot 3** (via `lot_inputs`). Lot 3 shipped to stores.
12 distinct illness cases link to stores that received lot 3.

Two directions of tracing are needed:

- **Backward** (already built, `GET /api/traceback/{lot_id}`): blended lot ->
  origin farms. Used for the "investigation priority / suspect origins".
- **Forward** (NEW, needed for this endpoint): recalled raw lot -> descendant
  blended lots -> shipments -> affected stores. Used for "which stores got it",
  stock-on-hold, and linked illness counts.

## Proposed response schema

`GET /api/incident/{recall_id}` -> JSON. Every field below is live-queryable;
the frontend merges these over the static layout/copy.

```jsonc
{
  "recall": {
    "id": 1,
    "product_id": 1,
    "product_name": "DEMO Romaine 1 kg",
    "lot_code": "DEMO-P1-RAW-A",
    "pathogen": "E. coli O157:H7",
    "status": "active",
    "created_at": "2026-10-23T16:00:00Z"
  },

  // -> merges into DATA.incident (title/summary strings are composed here)
  "incident": {
    "id": "DEMO-E01",                 // derived: "DEMO-E" + zero-padded recall id
    "activeSince": "09:00",           // recall.created_at, local time
    "pathogen": "E. coli O157:H7",
    "product_name": "DEMO Romaine 1 kg"
  },

  // -> DATA.stats VALUES (labels/tones stay static in data.js, matched by index)
  "stats": {
    "stores_received": 14,            // distinct stores that got any affected lot
    "stores_tracked": 21,             // total stores in the dataset
    "producers": 6,                   // farms + facilities touched by the trace
    "linked_cases": 12,               // distinct cases at affected stores
    "lab_positive": 2,                // positive lab_results among those
    "stock_on_hold_packs": 1063,      // sum inventory at affected stores
    "in_transit_stopped_packs": 320   // sum qty of in_transit affected shipments
  },

  // -> DATA.stores[].received  (merged by store id; x/y stay static)
  "store_status": [
    { "id": 1, "received": true },
    { "id": 2, "received": false }
    // ... one per store
  ],

  // -> DATA.chains (fully live from stores table)
  "chains": [
    {
      "name": "Target",
      "stores": [ { "id": 1, "city": "San Francisco" } ]
    }
  ],

  // -> DATA.investigation suspect ENTITIES (badge/tone/bullets copy stays
  //    static, matched by marker id). From backward traceback of affected lots.
  "suspects": [
    {
      "marker": "FA",
      "entity_type": "farm",
      "entity_id": 1,
      "name": "DEMO Farm A - North",
      "city": "Santa Rosa",
      "lab_positive": true            // a lot from this farm tested positive
    }
  ],

  // -> DATA.retail.rows (per-chain aggregates)
  "retail": [
    {
      "chain": "Target",
      "stores": 7,
      "withLot": 5,                   // stores in chain that got an affected lot
      "onHold": 380,                  // packs on hold at those stores
      "inbound": 113,                 // in-transit packs to those stores
      "reports": 5                    // cases linked to those stores
    }
  ],

  // -> DATA.facilities.rows (site/type/city live; role/action stay static copy)
  "facilities": [
    {
      "entity_id": 1,
      "site": "DEMO Farm A - North",
      "type": "Farm",
      "city": "Santa Rosa"
    }
  ]
}
```

## Field -> query mapping

| Response field | Source query (against db/schema.sql) |
|---|---|
| `recall.*` | `SELECT ... FROM recalls WHERE id = :recall_id` + join `products` for name |
| affected lot set | recall.lot_code -> `lots` -> recursive FORWARD walk of `lot_inputs` (input_lot_id -> output_lot_id) to collect the raw lot and all descendant lots |
| `incident.id` | composed: `'DEMO-E' + lpad(recall_id)` |
| `incident.activeSince` | `recalls.created_at` formatted to local time |
| `stats.stores_received` | `COUNT(DISTINCT to_store_id)` from `shipments` where `lot_id` in affected-lot set and `to_store_id` not null |
| `stats.stores_tracked` | `SELECT COUNT(*) FROM stores` |
| `stats.producers` | distinct farms+facilities appearing as lot origins / shipment sources in the affected set |
| `stats.linked_cases` | `COUNT(DISTINCT ce.case_id)` joining `case_exposures` -> stores that received affected lots (verified = 12) |
| `stats.lab_positive` | `COUNT` of `lab_results` with status='positive' tied to affected lots or those cases |
| `stats.stock_on_hold_packs` | sum of affected on-hand stock (from `supplier_inventory`/shipment state as modeled); see note |
| `stats.in_transit_stopped_packs` | `SUM(quantity)` from `shipments` where status='in_transit' and `lot_id` in affected set |
| `store_status[]` | all `stores` LEFT JOINed to whether they received an affected lot |
| `chains[]` | `stores` grouped by `chain` |
| `suspects[]` | backward traceback (`trace_origins`) of affected blended lots -> farms/facilities; `lab_positive` from `lab_results` |
| `retail[]` | per-chain aggregation of the store/shipment/case joins above |
| `facilities[]` | `farms` + `facilities` that appear in the affected lot origins/shipments |

## Open questions / dependencies (resolve before coding)

1. **Forward trace is new.** We have backward (`trace_origins`); we need a
   forward walk (recalled raw lot -> descendant lots). Small recursive CTE,
   mirror of the existing one. I'll add `trace_descendants(lot_id)` to
   `queries.py`.

2. **"Stock on hold" semantics.** The static demo shows 1,063 packs on hold.
   The schema models on-hand stock differently than the dataset's original
   `inventory` table (which we did NOT load; we mapped `supplier_offers` ->
   `supplier_inventory`). We need to decide what "on hold" means against the
   loaded schema: likely `SUM(quantity)` of delivered shipments of affected
   lots to stores. The exact number won't match the hardcoded 1,063 unless we
   define it to. **Recommendation:** define it as a clear, queryable figure and
   let the real number differ from the mockup's.

3. **Editorial fields stay static.** `investigation` badges/tones/bullets,
   `timeline`, `notifications.message`, and `footnote` are NOT in this endpoint.
   They remain in the trimmed `data.js`. The endpoint only supplies the
   entities/counts that drive them.

4. **Map coordinates stay static.** `stores[].x/y` and `producers[].x/y` are
   hand-placed for the 21-store demo set. The endpoint supplies `received`
   flags and entity identity only, merged by id.

## Frontend merge (app.js change, Phase B step 2)

```js
// before main():
async function loadLive() {
  try {
    const res = await fetch(`${API_BASE}/api/incident/1`);
    if (!res.ok) return;                 // fall back to static DATA
    const live = await res.json();
    mergeLive(DATA, live);               // overlay live fields by key/id
  } catch (_) { /* offline -> static DATA */ }
}
```

`mergeLive` overlays: incident counts, stat values (by index), store `received`
(by id), chains, suspect entities (by marker), retail rows (by chain),
facility rows (by id). Layout/copy untouched. If the fetch fails, the dashboard
still renders from the static `DATA` (graceful degradation for offline demo).
