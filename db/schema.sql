-- ============================================================
-- FOOD TRACEBACK + REPLACEMENT RECOMMENDATION DATABASE
-- PostgreSQL
-- ============================================================

-- ============================================================
-- TEARDOWN (makes this script re-runnable)
--
-- Drop tables first (CASCADE clears FK dependencies and any
-- dependent objects), then drop the enum types they used.
-- ============================================================
DROP TABLE IF EXISTS recall_shipment_flags CASCADE;
DROP TABLE IF EXISTS recalls              CASCADE;
DROP TABLE IF EXISTS lab_results          CASCADE;
DROP TABLE IF EXISTS case_exposures       CASCADE;
DROP TABLE IF EXISTS cases                CASCADE;
DROP TABLE IF EXISTS supplier_inventory   CASCADE;
DROP TABLE IF EXISTS shipments            CASCADE;
DROP TABLE IF EXISTS lot_inputs           CASCADE;
DROP TABLE IF EXISTS lots                 CASCADE;
DROP TABLE IF EXISTS products             CASCADE;
DROP TABLE IF EXISTS stores               CASCADE;
DROP TABLE IF EXISTS facilities           CASCADE;
DROP TABLE IF EXISTS farms                CASCADE;

DROP TYPE IF EXISTS recall_status     CASCADE;
DROP TYPE IF EXISTS shipment_status   CASCADE;
DROP TYPE IF EXISTS lab_result_status CASCADE;
DROP TYPE IF EXISTS facility_type     CASCADE;


-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE facility_type AS ENUM (
    'distributor',
    'packer',
    'processor'
);

CREATE TYPE lab_result_status AS ENUM (
    'positive',
    'negative',
    'pending'
);

CREATE TYPE shipment_status AS ENUM (
    'scheduled',
    'in_transit',
    'delivered',
    'hold_review',
    'cancelled'
);

CREATE TYPE recall_status AS ENUM (
    'active',
    'resolved'
);

-- ============================================================
-- CORE ENTITY TABLES
-- ============================================================
CREATE TABLE farms (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    city        VARCHAR(100),
    state       VARCHAR(50),
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE facilities (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    type        facility_type NOT NULL,
    city        VARCHAR(100),
    state       VARCHAR(50),
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stores (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    chain       VARCHAR(100),
    address     VARCHAR(200),
    city        VARCHAR(100),
    state       VARCHAR(50),
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- PRODUCTS
--
-- Extra product information is included so Bedrock can compare
-- a recalled product against possible replacements.
-- ============================================================
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    category        VARCHAR(80),
    description     TEXT,
    variety         VARCHAR(100),
    package_size    VARCHAR(50),
    unit            VARCHAR(30),
    attributes      JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- LOTS
--
-- Raw lots originate from farms.
-- Processed lots originate from facilities.
--
-- Exactly ONE of farm_id or facility_id must be present.
-- ============================================================
CREATE TABLE lots (
    id              SERIAL PRIMARY KEY,
    lot_code        VARCHAR(60) NOT NULL UNIQUE,
    product_id      INT NOT NULL
                    REFERENCES products(id),
    farm_id         INT
                    REFERENCES farms(id),
    facility_id     INT
                    REFERENCES facilities(id),
    production_date DATE NOT NULL,
    CONSTRAINT lot_has_one_origin CHECK (
        (farm_id IS NOT NULL AND facility_id IS NULL)
        OR
        (farm_id IS NULL AND facility_id IS NOT NULL)
    )
);

-- ============================================================
-- LOT INPUTS
--
-- Allows processed lots to contain multiple input lots.
--
-- Example:
--
-- Farm Lot A ----\
--                 ---> Processed Lot C
-- Farm Lot B ----/
--
-- This allows recursive traceback.
-- ============================================================
CREATE TABLE lot_inputs (
    output_lot_id INT NOT NULL
                  REFERENCES lots(id)
                  ON DELETE CASCADE,
    input_lot_id  INT NOT NULL
                  REFERENCES lots(id),
    PRIMARY KEY (
        output_lot_id,
        input_lot_id
    ),
    CHECK (
        output_lot_id <> input_lot_id
    )
);

-- ============================================================
-- SHIPMENTS
--
-- Tracks movement of food through the supply chain.
--
-- Source:
--     Farm OR Facility
--
-- Destination:
--     Facility OR Store
-- ============================================================
CREATE TABLE shipments (
    id                  SERIAL PRIMARY KEY,
    lot_id              INT NOT NULL
                        REFERENCES lots(id),
    from_farm_id        INT
                        REFERENCES farms(id),
    from_facility_id    INT
                        REFERENCES facilities(id),
    to_facility_id      INT
                        REFERENCES facilities(id),
    to_store_id         INT
                        REFERENCES stores(id),
    quantity            INT NOT NULL
                        CHECK (quantity > 0),
    status              shipment_status
                        NOT NULL
                        DEFAULT 'scheduled',
    shipped_at          TIMESTAMPTZ,
    estimated_arrival   TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ
                        NOT NULL
                        DEFAULT now(),
    CONSTRAINT one_source CHECK (
        (from_farm_id IS NOT NULL)::int
        +
        (from_facility_id IS NOT NULL)::int
        = 1
    ),
    CONSTRAINT one_destination CHECK (
        (to_facility_id IS NOT NULL)::int
        +
        (to_store_id IS NOT NULL)::int
        = 1
    )
);

-- ============================================================
-- SUPPLIER INVENTORY
--
-- THIS TABLE IS IMPORTANT FOR YOUR AI REPLACEMENT SYSTEM.
--
-- It tells the system:
--
-- 1. Who currently has a product?
-- 2. How much do they have?
-- 3. When can they supply it?
-- 4. What does it cost?
-- 5. How long does fulfillment normally take?
--
-- Supplier can be either a farm or facility.
-- ============================================================
CREATE TABLE supplier_inventory (
    id                          SERIAL PRIMARY KEY,
    farm_id                     INT
                                REFERENCES farms(id),
    facility_id                 INT
                                REFERENCES facilities(id),
    product_id                  INT NOT NULL
                                REFERENCES products(id),
    quantity_available          INT NOT NULL
                                DEFAULT 0
                                CHECK (quantity_available >= 0),
    unit_price                  NUMERIC(10,2)
                                CHECK (
                                    unit_price IS NULL
                                    OR unit_price >= 0
                                ),
    available_from              TIMESTAMPTZ
                                NOT NULL
                                DEFAULT now(),
    estimated_lead_time_hours   NUMERIC(8,2)
                                CHECK (
                                    estimated_lead_time_hours IS NULL
                                    OR estimated_lead_time_hours >= 0
                                ),
    is_available                BOOLEAN
                                NOT NULL
                                DEFAULT TRUE,
    updated_at                  TIMESTAMPTZ
                                NOT NULL
                                DEFAULT now(),
    CONSTRAINT inventory_one_supplier CHECK (
        (farm_id IS NOT NULL)::int
        +
        (facility_id IS NOT NULL)::int
        = 1
    )
);

-- ============================================================
-- ILLNESS CASES
-- ============================================================
CREATE TABLE cases (
    id          SERIAL PRIMARY KEY,
    onset_date  DATE NOT NULL,
    city        VARCHAR(100),
    state       VARCHAR(50),
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    pathogen    VARCHAR(80),
    raw_report  TEXT,
    created_at  TIMESTAMPTZ
                NOT NULL
                DEFAULT now()
);

-- ============================================================
-- CASE EXPOSURES
--
-- A case can be associated with:
--
-- - one or more stores
-- - one or more products
-- ============================================================
CREATE TABLE case_exposures (
    id              SERIAL PRIMARY KEY,
    case_id         INT NOT NULL
                    REFERENCES cases(id)
                    ON DELETE CASCADE,
    store_id        INT
                    REFERENCES stores(id),
    product_id      INT
                    REFERENCES products(id),
    exposure_date   DATE,
    CONSTRAINT exposure_has_target CHECK (
        store_id IS NOT NULL
        OR
        product_id IS NOT NULL
    )
);

-- ============================================================
-- LAB RESULTS
--
-- Lab result belongs to either:
--
-- - a food lot
-- OR
-- - a clinical case
-- ============================================================
CREATE TABLE lab_results (
    id          SERIAL PRIMARY KEY,
    lot_id      INT
                REFERENCES lots(id),
    case_id     INT
                REFERENCES cases(id),
    pathogen    VARCHAR(80) NOT NULL,
    status      lab_result_status
                NOT NULL
                DEFAULT 'pending',
    tested_on   DATE,
    CONSTRAINT lab_has_one_subject CHECK (
        (lot_id IS NOT NULL)::int
        +
        (case_id IS NOT NULL)::int
        = 1
    )
);

-- ============================================================
-- RECALLS
--
-- Stores official or internal food recall events.
--
-- raw_notice can contain the original FDA/USDA/etc. text.
--
-- Bedrock can extract structured information from raw_notice.
-- ============================================================
CREATE TABLE recalls (
    id              SERIAL PRIMARY KEY,
    product_id      INT
                    REFERENCES products(id),
    lot_code        VARCHAR(60),
    pathogen        VARCHAR(80),
    reason          TEXT,
    source          VARCHAR(100),
    source_url      TEXT,
    raw_notice      TEXT,
    status          recall_status
                    NOT NULL
                    DEFAULT 'active',
    created_at      TIMESTAMPTZ
                    NOT NULL
                    DEFAULT now()
);

-- ============================================================
-- RECALL SHIPMENT FLAGS
--
-- Keeps a record of WHY a shipment was flagged.
--
-- Do not rely only on changing shipment.status because we want
-- an audit trail explaining which recall caused the flag.
-- ============================================================
CREATE TABLE recall_shipment_flags (
    id              SERIAL PRIMARY KEY,
    recall_id       INT NOT NULL
                    REFERENCES recalls(id)
                    ON DELETE CASCADE,
    shipment_id     INT NOT NULL
                    REFERENCES shipments(id)
                    ON DELETE CASCADE,
    reason          TEXT NOT NULL,
    review_status   VARCHAR(30)
                    NOT NULL
                    DEFAULT 'needs_review',
    created_at      TIMESTAMPTZ
                    NOT NULL
                    DEFAULT now(),
    UNIQUE (
        recall_id,
        shipment_id
    )
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_lots_farm
ON lots(farm_id);

CREATE INDEX idx_lots_facility
ON lots(facility_id);

CREATE INDEX idx_lots_product
ON lots(product_id);

CREATE INDEX idx_lot_inputs_input
ON lot_inputs(input_lot_id);

CREATE INDEX idx_lot_inputs_output
ON lot_inputs(output_lot_id);

CREATE INDEX idx_shipments_lot
ON shipments(lot_id);

CREATE INDEX idx_shipments_to_store
ON shipments(to_store_id);

CREATE INDEX idx_shipments_to_fac
ON shipments(to_facility_id);

CREATE INDEX idx_shipments_status
ON shipments(status);

CREATE INDEX idx_shipments_shipped_at
ON shipments(shipped_at);

CREATE INDEX idx_cases_onset
ON cases(onset_date);

CREATE INDEX idx_exposures_case
ON case_exposures(case_id);

CREATE INDEX idx_exposures_store
ON case_exposures(store_id);

CREATE INDEX idx_exposures_product
ON case_exposures(product_id);

CREATE INDEX idx_lab_lot
ON lab_results(lot_id);

CREATE INDEX idx_supplier_inventory_product
ON supplier_inventory(product_id);

CREATE INDEX idx_supplier_inventory_farm
ON supplier_inventory(farm_id);

CREATE INDEX idx_supplier_inventory_facility
ON supplier_inventory(facility_id);

CREATE INDEX idx_supplier_inventory_available
ON supplier_inventory(is_available);

CREATE INDEX idx_recalls_product
ON recalls(product_id);

CREATE INDEX idx_recalls_lot
ON recalls(lot_code);

CREATE INDEX idx_recall_flags_recall
ON recall_shipment_flags(recall_id);

CREATE INDEX idx_recall_flags_shipment
ON recall_shipment_flags(shipment_id);
