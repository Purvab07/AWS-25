// ============================================================================
// Incident Console — synthetic demo data
// All farms, facilities, lots, inventory, illness reports and lab results are
// synthetic. Store names/addresses are real public locations. No real outbreak
// is alleged. Map is schematic.
// ============================================================================

const DATA = {
  incident: {
    id: "DEMO-E01",
    activeSince: "10:00",
    title:
      "DEMO Romaine 1 kg · Raw lot DEMO-P1-RAW-A and blended lot DEMO-P1-BLEND-A · E. coli O157:H7",
    summary:
      "Blended lot reached 14 of 21 sampled stores. 6 illness reports are linked (2 lab-positive). Reports show association by store visit, not proven cause.",
  },

  // --- KPI stat cards -------------------------------------------------------
  stats: [
    {
      label: "Retail stores tracked",
      value: "21",
      detail: "14 received the recalled lot · 3 chains",
      tone: "default",
    },
    {
      label: "Producers and sites",
      value: "6",
      detail: "2 farms · 1 packer · 3 warehouses",
      tone: "default",
    },
    {
      label: "Linked illness reports",
      value: "6",
      detail: "2 lab-positive · 4 pending · 1 hospitalization",
      tone: "warn",
    },
    {
      label: "Stock on hold",
      value: "1,063",
      detail: "packs · 320 more in transit stopped",
      tone: "danger",
    },
    {
      label: "Notices sent",
      value: "0 / 9",
      detail: "drafted, awaiting approval",
      tone: "info",
    },
  ],

  // --- Map filters ----------------------------------------------------------
  mapFilters: ["Stores", "Producers", "Illness reports", "Trace lines"],

  // --- Store markers on the schematic map -----------------------------------
  // x / y are percentages of the map area. received = got recalled lot (red).
  stores: [
    { id: 1,  x: 22, y: 71, received: true },
    { id: 2,  x: 20, y: 79, received: false },
    { id: 3,  x: 25, y: 86, received: true },
    { id: 4,  x: 29, y: 92, received: true },
    { id: 5,  x: 31, y: 73, received: true },
    { id: 6,  x: 52, y: 62, received: false },
    { id: 7,  x: 20, y: 36, received: true },
    { id: 8,  x: 37, y: 76, received: false },
    { id: 9,  x: 42, y: 83, received: true },
    { id: 10, x: 48, y: 89, received: true },
    { id: 11, x: 33, y: 90, received: false },
    { id: 12, x: 32, y: 64, received: true },
    { id: 13, x: 54, y: 43, received: true },
    { id: 14, x: 40, y: 40, received: false },
    { id: 15, x: 33, y: 68, received: true },
    { id: 16, x: 24, y: 72, received: true },
    { id: 17, x: 15, y: 56, received: false },
    { id: 18, x: 42, y: 34, received: true },
    { id: 19, x: 52, y: 93, received: true },
    { id: 20, x: 29, y: 67, received: true },
    { id: 21, x: 48, y: 65, received: false },
  ],

  // --- Producer / facility markers -----------------------------------------
  producers: [
    { id: "FA", x: 13, y: 34, kind: "farm",      label: "DEMO Farm A · investigate", callout: true },
    { id: "FB", x: 37, y: 42, kind: "farm" },
    { id: "PK", x: 27, y: 61, kind: "packer" },
    { id: "W1", x: 24, y: 51, kind: "warehouse" },
    { id: "W2", x: 38, y: 68, kind: "warehouse" },
    { id: "W3", x: 36, y: 86, kind: "warehouse" },
    { id: "C1", x: 20, y: 66, kind: "illness" },
    { id: "C2", x: 23, y: 83, kind: "illness" },
    { id: "C3", x: 32, y: 86, kind: "illness" },
    { id: "C4", x: 50, y: 58, kind: "illness" },
    { id: "C5", x: 18, y: 32, kind: "illness" },
    { id: "C6", x: 40, y: 78, kind: "illness" },
  ],

  // --- Map key: store chains ------------------------------------------------
  chains: [
    {
      name: "Target · 7 stores",
      stores: [
        { id: 1, city: "San Francisco" },
        { id: 2, city: "Colma" },
        { id: 3, city: "Redwood City" },
        { id: 4, city: "Sunnyvale" },
        { id: 5, city: "Alameda" },
        { id: 6, city: "Walnut Creek" },
        { id: 7, city: "Santa Rosa" },
      ],
    },
    {
      name: "Walmart · 7 stores",
      stores: [
        { id: 8, city: "San Leandro" },
        { id: 9, city: "Union City" },
        { id: 10, city: "Milpitas" },
        { id: 11, city: "Mountain View" },
        { id: 12, city: "Richmond" },
        { id: 13, city: "Fairfield" },
        { id: 14, city: "Napa" },
      ],
    },
    {
      name: "Whole Foods Market · 7 stores",
      stores: [
        { id: 15, city: "Oakland" },
        { id: 16, city: "San Francisco" },
        { id: 17, city: "San Rafael" },
        { id: 18, city: "Napa" },
        { id: 19, city: "San Jose" },
        { id: 20, city: "Berkeley" },
        { id: 21, city: "Walnut Creek" },
      ],
    },
  ],

  // --- Map key: facilities --------------------------------------------------
  facilityKey: [
    { id: "FA", name: "DEMO Farm A", sub: "Santa Rosa" },
    { id: "FB", name: "DEMO Farm B", sub: "Napa" },
    { id: "PK", name: "DEMO Produce Packer", sub: "Richmond" },
    { id: "W1", name: "Novato Warehouse", sub: "Distributor" },
    { id: "W2", name: "Oakland Warehouse", sub: "Distributor" },
    { id: "W3", name: "San Jose Warehouse", sub: "Distributor" },
    { id: "C1", name: "Illness reports C1–C6", sub: "Placed at the store visited" },
  ],

  // --- Investigation priority cards ----------------------------------------
  investigation: [
    {
      badge: "HIGH",
      tone: "danger",
      marker: "FA",
      title: "DEMO Farm A - North",
      meta: "Farm · Santa Rosa",
      bullets: [
        "Raw lot tested positive for E. coli O157:H7",
        "Its lot went into the recalled blend",
        "Offer to retailers is on hold",
      ],
      action: { label: "Notify to investigate", tone: "danger" },
    },
    {
      badge: "HIGH",
      tone: "danger",
      marker: "PK",
      title: "DEMO Produce Packer",
      meta: "Packer · Richmond",
      bullets: [
        "Blended raw lots A and B into the recalled lot",
        "Shipped it on to 3 warehouses",
      ],
      action: { label: "Notify to investigate", tone: "danger" },
    },
    {
      badge: "REVIEW",
      tone: "warn",
      marker: "FB",
      title: "DEMO Farm B - Alternate",
      meta: "Farm · Napa",
      bullets: [
        "Raw lot also went into the recalled blend",
        "Lot is released and untested as a source. Possible origin only, cause not assigned",
      ],
      action: { label: "Request records", tone: "warn" },
    },
    {
      badge: "ACTION",
      tone: "info",
      title: "3 distribution warehouses",
      bullets: [
        "320 packs in transit are flagged to stop. Confirm outbound holds in Novato, Oakland and San Jose.",
      ],
    },
  ],

  // --- Retail customers table ----------------------------------------------
  retail: {
    caption: "21 stores · 3 chains",
    rows: [
      { chain: "Target",              stores: 7, withLot: 5, onHold: 380, inbound: 113, reports: 5, status: "Notice needed" },
      { chain: "Walmart",             stores: 7, withLot: 4, onHold: 286, inbound: 89,  reports: 2, status: "Notice needed" },
      { chain: "Whole Foods Market",  stores: 7, withLot: 5, onHold: 397, inbound: 118, reports: 2, status: "Notice needed" },
    ],
  },

  // --- Producers & facilities table ----------------------------------------
  facilities: {
    caption: "2 farms · 1 packer · 3 warehouses",
    rows: [
      { site: "DEMO Farm A - North",    type: "Farm",        city: "Santa Rosa", role: "Source of positive raw lot",         action: "Investigate" },
      { site: "DEMO Produce Packer",    type: "Packer",      city: "Richmond",   role: "Blended raw lots A + B into recalled lot", action: "Investigate" },
      { site: "DEMO Farm B - Alternate",type: "Farm",        city: "Napa",       role: "Raw lot fed the blend, not recalled", action: "Review records" },
      { site: "DEMO Novato Warehouse",  type: "Distributor", city: "Novato",     role: "Shipped recalled lot to stores",     action: "Stop outbound" },
      { site: "DEMO Oakland Warehouse", type: "Distributor", city: "Oakland",    role: "Shipped recalled lot to stores",     action: "Stop outbound" },
      { site: "DEMO San Jose Warehouse",type: "Distributor", city: "San Jose",   role: "Shipped recalled lot to stores",     action: "Stop outbound" },
    ],
  },

  // --- Event timeline -------------------------------------------------------
  timeline: {
    caption: "4 of 6 steps done · notices awaiting approval",
    steps: [
      { state: "DONE",        title: "Illness report received", time: "09:00 · retailer", note: "Synthetic illness report." },
      { state: "DONE",        title: "Raw lot tests positive",  time: "09:20 · lab",      note: "Raw lot 1 sample positive." },
      { state: "DONE",        title: "Recall active",           time: "10:00 · admin",    note: "Raw lot 1 and descendant blended lot 3." },
      { state: "DONE",        title: "Shipments flagged",       time: "10:10 · system",   note: "320 packs in transit flagged to stop." },
      { state: "IN PROGRESS", title: "Replacement review",      time: "10:20 · retailer", note: "Retailers reviewing safe alternative lots." },
      { state: "NOT STARTED", title: "Investigation notices",   time: "Awaiting approval",note: "0 of 9 drafted notices sent." },
    ],
  },

  // --- Send notifications ----------------------------------------------------
  notifications: {
    caption: "Recipients · 9 notices",
    recipients: [
      { title: "DEMO Farm A - North",      detail: "investigate positive raw lot",      checked: true },
      { title: "DEMO Produce Packer",      detail: "provide blending records",          checked: true },
      { title: "DEMO Farm B - Alternate",  detail: "provide records for raw lot B",      checked: true },
      { title: "3 distribution warehouses",detail: "stop outbound lot 3",                checked: true },
      { title: "3 grocery chains, 14 stores", detail: "hold and remove stock",          checked: true },
    ],
    message:
      "Recall DEMO-E01 (DEMO Romaine 1 kg): raw lot DEMO-P1-RAW-A tested positive for E. coli O157:H7. Pause distribution of blended lot DEMO-P1-BLEND-A, preserve all records for lots linked to it, and expect investigator contact within 24 hours. Synthetic demo message.",
  },

  footnote:
    "Snapshot: Oct 23, 2026, 12:00 PDT. Store names and addresses are real public locations; all farms, facilities, lots, inventory, prices, illness reports and lab results are synthetic. No real outbreak is alleged. Map is schematic.",
};
