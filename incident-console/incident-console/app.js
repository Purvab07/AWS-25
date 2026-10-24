// ============================================================================
// Incident Console — renderer + interactivity (vanilla JS, no dependencies)
// ============================================================================

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};

// --- Header ---------------------------------------------------------------
function renderHeader() {
  const { incident } = DATA;
  const root = $("#header");
  root.innerHTML = `
    <div class="brand">
      <div class="logo"></div>
      <div>
        <h1>Incident console</h1>
        <div class="sub">Regulator view · Regional food safety authority (demo) · Bay Area, California</div>
      </div>
    </div>
    <div class="header-right">
      <div class="toggle" id="view-toggle">
        <button data-view="retailer">Retailer</button>
        <button data-view="regulator" class="active">Regulator</button>
      </div>
      <span class="badge-synthetic">SYNTHETIC DEMO DATA</span>
    </div>`;

  root.querySelectorAll("#view-toggle button").forEach((b) => {
    b.addEventListener("click", () => {
      root.querySelectorAll("#view-toggle button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
    });
  });
}

// --- Incident banner ------------------------------------------------------
function renderBanner() {
  const { incident } = DATA;
  $("#banner").innerHTML = `
    <div>
      <div class="kicker">${incident.id} · RECALL ACTIVE SINCE ${incident.activeSince}</div>
      <h2>${incident.title}</h2>
      <p>${incident.summary}</p>
    </div>
    <div class="banner-actions">
      <button class="btn btn-ghost" data-toast="Trace report exported (demo)">Export trace report</button>
      <button class="btn btn-primary" data-toast="Investigation notices drafted (demo)">Send investigation notices</button>
    </div>`;
}

// --- Stat cards -----------------------------------------------------------
function renderStats() {
  const wrap = $("#stats");
  wrap.innerHTML = "";
  DATA.stats.slice(0, 4).forEach((s) => wrap.appendChild(statCard(s)));

  const wide = $("#stat-wide");
  wide.innerHTML = "";
  wide.appendChild(statCard(DATA.stats[4]));
}
function statCard(s) {
  return el(
    "div",
    `panel stat tone-${s.tone}`,
    `<div class="label">${s.label}</div>
     <div class="value">${s.value}</div>
     <div class="detail">${s.detail}</div>`
  );
}

// --- Map ------------------------------------------------------------------
const CITY_LABELS = [
  { name: "Santa Rosa", x: 24, y: 30 },
  { name: "Napa", x: 44, y: 38 },
  { name: "Fairfield", x: 61, y: 42 },
  { name: "Vallejo", x: 45, y: 49 },
  { name: "Walnut Creek", x: 60, y: 62 },
  { name: "Oakland", x: 40, y: 69 },
  { name: "San Francisco", x: 18, y: 72 },
  { name: "Palo Alto", x: 36, y: 86 },
  { name: "San Jose", x: 54, y: 95 },
  { name: "Santa Cruz", x: 36, y: 99 },
];
const HIGHWAYS = [
  { n: "101", x: 10, y: 42 }, { n: "280", x: 18, y: 82 }, { n: "880", x: 46, y: 60 },
  { n: "680", x: 60, y: 70 }, { n: "580", x: 62, y: 76 }, { n: "85", x: 42, y: 92 },
  { n: "17", x: 40, y: 96 }, { n: "80", x: 62, y: 36 },
];

// Real interactive map (Leaflet + OpenStreetMap). Uses live lat/lng from the
// API (DATA._geo). Falls back to a simple message if Leaflet or geo data is
// unavailable (offline / API down).
let _leafletMap = null;
const _mapLayers = {}; // group name -> L.layerGroup

function circleMarker(lat, lng, color, radius, popup) {
  const m = L.circleMarker([lat, lng], {
    radius,
    color: "#0a1526",
    weight: 1,
    fillColor: color,
    fillOpacity: 0.9,
  });
  if (popup) m.bindPopup(popup);
  return m;
}

function renderMap() {
  // Filter chips (same UI; now toggle Leaflet layers)
  $("#map-filters").innerHTML = DATA.mapFilters
    .map((f) => `<button class="chip active" data-filter="${f}">${f}</button>`)
    .join("");

  const geo = DATA._geo;
  const haveLeaflet = typeof L !== "undefined";
  const haveGeo = geo && geo.stores && geo.stores.some((s) => s.lat != null);

  if (!haveLeaflet || !haveGeo) {
    $("#map").innerHTML =
      `<div style="padding:24px;color:var(--text-dim);font-size:13px">` +
      `Map unavailable (live location data or map library not loaded).</div>`;
    wireMapFilters();
    return;
  }

  // (Re)create the Leaflet map on the #map div.
  const mapEl = $("#map");
  mapEl.innerHTML = "";
  if (_leafletMap) { _leafletMap.remove(); _leafletMap = null; }
  const map = L.map(mapEl, { zoomControl: true, scrollWheelZoom: true });
  _leafletMap = map;

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // --- layer groups keyed to the filter chip names ------------------------
  const stores = L.layerGroup();
  const producers = L.layerGroup();
  const illness = L.layerGroup();
  const trace = L.layerGroup();
  _mapLayers["Stores"] = stores;
  _mapLayers["Producers"] = producers;
  _mapLayers["Illness reports"] = illness;
  _mapLayers["Trace lines"] = trace;

  const bounds = [];

  // Store markers: red = received the recalled lot, grey = did not.
  geo.stores.forEach((s) => {
    if (s.lat == null || s.lng == null) return;
    const color = s.received ? "#ff4d5e" : "#5b6b84";
    const popup =
      `<b>${s.name || "Store " + s.id}</b><br>${s.chain || ""} · ${s.city || ""}` +
      `<br>${s.received ? "Received the recalled lot" : "Did not receive the lot"}`;
    circleMarker(s.lat, s.lng, color, 7, popup).addTo(stores);
    bounds.push([s.lat, s.lng]);
  });

  // Producer markers: farms + the blending facility.
  const prodColor = { farm: "#f5c518", packer: "#8b5cf6", processor: "#8b5cf6", distributor: "#38bdf8" };
  geo.producers.forEach((p) => {
    if (p.lat == null || p.lng == null) return;
    const color = prodColor[p.kind] || "#f5c518";
    const popup = `<b>${p.name}</b><br>${p.kind} · ${p.city || ""}`;
    circleMarker(p.lat, p.lng, color, 9, popup).addTo(producers);
    bounds.push([p.lat, p.lng]);
  });

  // Illness case markers (if any have coordinates).
  (geo.cases || []).forEach((c) => {
    if (c.lat == null || c.lng == null) return;
    circleMarker(c.lat, c.lng, "#fb923c", 6,
      `<b>Illness report</b><br>${c.city || ""} · ${c.pathogen || "unknown"}`).addTo(illness);
    bounds.push([c.lat, c.lng]);
  });

  // Trace lines: from each producer to the stores that received the lot.
  const receivedStores = geo.stores.filter((s) => s.received && s.lat != null);
  geo.producers
    .filter((p) => p.kind !== "farm" && p.lat != null)
    .forEach((p) => {
      receivedStores.forEach((s) => {
        L.polyline([[p.lat, p.lng], [s.lat, s.lng]], {
          color: "#ff4d5e", weight: 1, opacity: 0.25,
        }).addTo(trace);
      });
    });

  // All layers on by default (matches all-active chips).
  stores.addTo(map);
  producers.addTo(map);
  illness.addTo(map);
  trace.addTo(map);

  if (bounds.length) {
    map.fitBounds(bounds, { padding: [30, 30] });
  } else {
    map.setView([37.8, -122.3], 9); // Bay Area fallback
  }

  wireMapFilters();
}

function wireMapFilters() {
  $("#map-filters").querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("active");
      chip.classList.toggle("off");
      applyMapFilters();
    });
  });
}

function applyMapFilters() {
  if (!_leafletMap) return;
  const active = new Set(
    [...$("#map-filters").querySelectorAll(".chip.active")].map((c) => c.dataset.filter)
  );
  Object.entries(_mapLayers).forEach(([name, layer]) => {
    if (active.has(name)) {
      if (!_leafletMap.hasLayer(layer)) layer.addTo(_leafletMap);
    } else if (_leafletMap.hasLayer(layer)) {
      _leafletMap.removeLayer(layer);
    }
  });
}

// --- Map key --------------------------------------------------------------
function renderMapKey() {
  const root = $("#map-key");
  const cols = DATA.chains
    .map(
      (c) => `
      <div class="key-col">
        <h5>${c.name}</h5>
        ${c.stores
          .map(
            (s) => `<div class="key-store"><span class="dot">${s.id}</span>${s.city}</div>`
          )
          .join("")}
      </div>`
    )
    .join("");
  root.innerHTML = `
    <h4>Map key · what the labels mean</h4>
    <p class="lede">Numbered circles are the 21 grocery stores, grouped by chain below.
      <span class="danger-text">Red</span> = received the recalled lot, grey = did not.</p>
    <div class="key-cols">${cols}</div>`;
}

// --- Investigation priority ----------------------------------------------
function renderInvestigation() {
  const root = $("#investigation");
  root.innerHTML = `<div class="eyebrow section-title">Investigation priority</div>`;
  DATA.investigation.forEach((c) => {
    const card = el("div", `panel invest-card ${c.tone}`);
    const head = `
      <div class="invest-head">
        <span class="pill ${c.tone}">${c.badge}</span>
        ${c.marker ? `<span class="inv-marker ${c.marker}">${c.marker}</span>` : ""}
        <div>
          <h3>${c.title}</h3>
          ${c.meta ? `<div class="meta">${c.meta}</div>` : ""}
        </div>
      </div>`;
    if (c.tone === "info") {
      card.innerHTML = `
        <div class="invest-head"><span class="pill info">${c.badge}</span></div>
        <h3>${c.title}</h3>
        <p class="desc">${c.bullets.join(" ")}</p>`;
    } else {
      card.innerHTML =
        head +
        `<ul>${c.bullets.map((b) => `<li>${b}</li>`).join("")}</ul>` +
        `<button class="btn btn-${c.action.tone}" data-toast="${c.title}: ${c.action.label} (demo)">${c.action.label}</button>`;
    }
    root.appendChild(card);
  });
}

// --- Retail table ---------------------------------------------------------
function renderRetail() {
  const { retail } = DATA;
  $("#retail").innerHTML = `
    <div class="tbl-head">
      <span class="eyebrow">Retail customers in area</span>
      <span class="faint">${retail.caption}</span>
    </div>
    <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>Chain</th><th class="num">Stores</th><th class="num">With lot</th>
        <th class="num">On hold</th><th class="num">Inbound</th><th class="num">Reports</th><th>Status</th>
      </tr></thead>
      <tbody>
        ${retail.rows
          .map(
            (r) => `<tr>
          <td class="strong">${r.chain}</td>
          <td class="num">${r.stores}</td>
          <td class="num">${r.withLot}</td>
          <td class="num">${r.onHold}</td>
          <td class="num">${r.inbound}</td>
          <td class="num">${r.reports}</td>
          <td class="status-need">${r.status}</td>
        </tr>`
          )
          .join("")}
      </tbody>
    </table></div>
    <div class="caption">Stock in packs.</div>`;
}

// --- Facilities table -----------------------------------------------------
function renderFacilities() {
  const { facilities } = DATA;
  const actionCls = (a) =>
    a === "Stop outbound" || a === "Investigate" ? "action-link danger" : "action-link";
  $("#facilities").innerHTML = `
    <div class="tbl-head">
      <span class="eyebrow">Producers and facilities in area</span>
      <span class="faint">${facilities.caption}</span>
    </div>
    <div class="tbl-wrap">
    <table>
      <thead><tr><th>Site</th><th>Type</th><th>City</th><th>Role in this recall</th><th>Action</th></tr></thead>
      <tbody>
        ${facilities.rows
          .map(
            (r) => `<tr>
          <td class="strong">${r.site}</td>
          <td class="muted">${r.type}</td>
          <td class="muted">${r.city}</td>
          <td class="muted">${r.role}</td>
          <td class="${actionCls(r.action)}" data-toast="${r.site}: ${r.action} (demo)">${r.action}</td>
        </tr>`
          )
          .join("")}
      </tbody>
    </table></div>`;
}

// --- Timeline -------------------------------------------------------------
function renderTimeline() {
  const { timeline } = DATA;
  const cls = { DONE: "done", "IN PROGRESS": "progress", "NOT STARTED": "notstarted" };
  const icon = { DONE: "✓", "IN PROGRESS": "●", "NOT STARTED": "○" };
  $("#timeline").innerHTML = `
    <div class="tbl-head">
      <span class="eyebrow">Event timeline</span>
      <span class="faint">${timeline.caption}</span>
    </div>
    <div class="timeline-steps">
      ${timeline.steps
        .map(
          (s) => `<div class="tstep ${cls[s.state]}">
          <div class="node">${icon[s.state]}</div>
          <div class="line"></div>
          <span class="tstate ${cls[s.state]}">${s.state}</span>
          <h4>${s.title}</h4>
          <div class="ttime">${s.time}</div>
          <div class="tnote">${s.note}</div>
        </div>`
        )
        .join("")}
    </div>`;
}

// --- Notifications --------------------------------------------------------
function renderNotifications() {
  const { notifications } = DATA;
  $("#notify").innerHTML = `
    <div class="tbl-head">
      <span class="eyebrow">Send notifications</span>
      <span class="faint">${notifications.caption}</span>
    </div>
    ${notifications.recipients
      .map(
        (r, i) => `<label class="recipient">
        <input type="checkbox" ${r.checked ? "checked" : ""} data-recipient="${i}"/>
        <span><span class="r-title">${r.title}</span> <span class="r-detail">· ${r.detail}</span></span>
      </label>`
      )
      .join("")}
    <label class="msg-label">Message</label>
    <textarea id="notify-msg">${notifications.message}</textarea>
    <div class="notify-actions">
      <button class="btn btn-ghost" data-toast="Notice preview opened (demo)">Preview</button>
      <button class="btn btn-primary" id="send-notices">Send 9 notices</button>
    </div>`;

  const updateSendLabel = () => {
    const n = $("#notify").querySelectorAll("input[data-recipient]:checked").length;
    // each recipient line can represent multiple notices; keep headline count simple
    $("#send-notices").textContent = `Send ${n ? 9 : 0} notices`;
  };
  $("#notify")
    .querySelectorAll("input[data-recipient]")
    .forEach((c) => c.addEventListener("change", updateSendLabel));
  $("#send-notices").addEventListener("click", () =>
    toast("9 investigation notices queued for approval (demo)")
  );
}

// --- Footnote -------------------------------------------------------------
function renderFootnote() {
  $("#footnote").textContent = DATA.footnote;
}

// --- Toast (demo feedback) ------------------------------------------------
let toastTimer;
function toast(msg) {
  let t = $("#toast");
  if (!t) {
    t = el("div", "", "");
    t.id = "toast";
    Object.assign(t.style, {
      position: "fixed", bottom: "24px", left: "50%", transform: "translateX(-50%)",
      background: "#16263f", color: "#e6edf6", border: "1px solid #1e3250",
      padding: "12px 18px", borderRadius: "10px", fontSize: "13px", fontWeight: "600",
      boxShadow: "0 8px 24px rgba(0,0,0,0.45)", zIndex: 999, opacity: 0,
      transition: "opacity .2s ease",
    });
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = 1;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.style.opacity = 0), 2200);
}
// global delegation for demo buttons
document.addEventListener("click", (e) => {
  const trg = e.target.closest("[data-toast]");
  if (trg) toast(trg.dataset.toast);
});

// --- Live data (Phase B) --------------------------------------------------
// Fetch the live incident snapshot from the backend API and overlay it onto
// the static DATA object. Map layout (x/y coords) and editorial copy stay
// static; only data-backed fields are overwritten. If the API is unreachable,
// the dashboard falls back to the hardcoded DATA (offline-safe).
const API_BASE = "http://localhost:8000";
const INCIDENT_ID = 1;

async function loadLive() {
  let live;
  try {
    const res = await fetch(`${API_BASE}/api/incident/${INCIDENT_ID}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    live = await res.json();
  } catch (err) {
    console.warn("Live data unavailable, using static DATA:", err.message);
    return false; // graceful fallback
  }
  mergeLive(live);
  return true;
}

function mergeLive(live) {
  // --- incident id + active-since (keep curated title/summary) -------------
  if (live.incident) {
    if (live.incident.id) DATA.incident.id = live.incident.id;
    if (live.incident.activeSince)
      DATA.incident.activeSince = live.incident.activeSince;
  }

  // --- stat card values, matched by label keyword -------------------------
  // Static labels/tones are kept; only the numeric value is overlaid for the
  // cards we have live figures for.
  const s = live.stats || {};
  const setStat = (match, value, detail) => {
    const card = DATA.stats.find((c) => c.label.toLowerCase().includes(match));
    if (card && value != null) {
      card.value = String(value);
      if (detail) card.detail = detail;
    }
  };
  setStat("stores tracked", s.stores_tracked,
    `${s.stores_received} received the recalled lot · ${DATA.chains.length} chains`);
  setStat("producers", s.producers);
  setStat("illness", s.linked_cases,
    `${s.lab_positive} lab-positive · linked by store visit`);

  // --- store received flags, merged by id ---------------------------------
  if (Array.isArray(live.store_status)) {
    const recv = new Map(live.store_status.map((x) => [x.id, x.received]));
    DATA.stores.forEach((st) => {
      if (recv.has(st.id)) st.received = recv.get(st.id);
    });
  }

  // --- chains: replace wholesale (same shape) -----------------------------
  if (Array.isArray(live.chains) && live.chains.length) {
    DATA.chains = live.chains.map((c) => ({
      name: `${c.name} · ${c.stores.length} stores`,
      stores: c.stores,
    }));
  }

  // --- geo data for the real map (stores/producers/cases with lat/lng) ----
  DATA._geo = {
    stores: live.store_status || [],
    producers: live.producers || [],
    cases: live.cases || [],
  };

  // --- mark that live data is in use (small UI signal) --------------------
  DATA._live = true;
}

// --- Boot -----------------------------------------------------------------
function main() {
  renderHeader();
  renderBanner();
  renderStats();
  renderMap();
  renderMapKey();
  renderInvestigation();
  renderRetail();
  renderFacilities();
  renderTimeline();
  renderNotifications();
  renderFootnote();
}

async function boot() {
  await loadLive(); // overlay live data if the API is reachable
  main();
}
document.addEventListener("DOMContentLoaded", boot);
