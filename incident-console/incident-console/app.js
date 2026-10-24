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

function renderMap() {
  $("#map-filters").innerHTML = DATA.mapFilters
    .map((f) => `<button class="chip active" data-filter="${f}">${f}</button>`)
    .join("");

  const map = $("#map");
  // base svg (schematic coastline + bay)
  map.innerHTML = `
    <svg class="geo" viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        <linearGradient id="land" x1="0" x2="1">
          <stop offset="0" stop-color="#15263f"/><stop offset="1" stop-color="#112036"/>
        </linearGradient>
      </defs>
      <path d="M30,0 L100,0 L100,100 L40,100 L44,88 L36,78 L40,66 L30,60 L34,50 L28,40 L34,30 L26,22 L32,10 Z"
            fill="url(#land)" stroke="#20374f" stroke-width="0.4"/>
      <path d="M34,50 L40,55 L42,64 L38,72 L44,78 L40,88 L44,100"
            fill="none" stroke="#1b3352" stroke-width="0.5" opacity="0.8"/>
      <g stroke="#27496e" stroke-width="0.35" opacity="0.6" fill="none">
        <path d="M10,42 L30,55 L46,60 L62,70"/>
        <path d="M18,82 L46,60 L62,36"/>
        <path d="M60,70 L62,76 L42,92 L40,96"/>
      </g>
    </svg>
    <div class="trace-layer" id="trace-layer"></div>
    <div class="ocean-label">PACIFIC OCEAN</div>
    <div class="map-zoom">
      <button data-toast="Zoom in (demo)">+</button>
      <button data-toast="Zoom out (demo)">−</button>
      <button class="fit" data-toast="Fit to view (demo)">Fit</button>
    </div>`;

  // trace lines (SVG overlay, percentage coords)
  const packer = DATA.producers.find((p) => p.id === "PK");
  const traceTargets = DATA.stores.filter((s) => s.received).slice(0, 10);
  const traceSvg = `<svg class="geo" viewBox="0 0 100 100" preserveAspectRatio="none" style="z-index:1">
    ${traceTargets
      .map(
        (t) =>
          `<line x1="${packer.x}" y1="${packer.y}" x2="${t.x}" y2="${t.y}" stroke="#ff4d5e" stroke-width="0.25" opacity="0.4"/>`
      )
      .join("")}
    <line x1="13" y1="34" x2="${packer.x}" y2="${packer.y}" stroke="#f5c518" stroke-width="0.3" stroke-dasharray="1 1" opacity="0.6"/>
    <line x1="37" y1="42" x2="${packer.x}" y2="${packer.y}" stroke="#f5c518" stroke-width="0.3" stroke-dasharray="1 1" opacity="0.6"/>
  </svg>`;
  $("#trace-layer").innerHTML = traceSvg;

  // city + highway labels
  CITY_LABELS.forEach((c) => {
    const n = el("div", "city-label", c.name);
    n.style.left = c.x + "%"; n.style.top = c.y + "%";
    map.appendChild(n);
  });
  HIGHWAYS.forEach((h) => {
    const n = el("div", "hwy", h.n);
    n.style.left = h.x + "%"; n.style.top = h.y + "%";
    map.appendChild(n);
  });

  // store markers
  DATA.stores.forEach((s) => {
    const n = el("div", `marker store ${s.received ? "recv" : "norecv"}`, String(s.id));
    n.style.left = s.x + "%"; n.style.top = s.y + "%";
    n.dataset.group = "Stores";
    n.title = `Store ${s.id} — ${s.received ? "received recalled lot" : "did not receive lot"}`;
    map.appendChild(n);
  });

  // producer / facility / illness markers
  DATA.producers.forEach((p) => {
    const group = p.kind === "illness" ? "Illness reports" : "Producers";
    let cls = "marker ";
    if (p.kind === "illness") cls += "illness";
    else cls += `facility ${p.kind}`;
    const n = el("div", cls, p.id);
    n.style.left = p.x + "%"; n.style.top = p.y + "%";
    n.dataset.group = group;
    if (p.callout) n.appendChild(el("div", "callout", "DEMO Farm A · investigate"));
    map.appendChild(n);
  });

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
  const active = new Set(
    [...$("#map-filters").querySelectorAll(".chip.active")].map((c) => c.dataset.filter)
  );
  document.querySelectorAll("#map .marker").forEach((m) => {
    m.style.display = active.has(m.dataset.group) ? "" : "none";
  });
  const tl = $("#trace-layer");
  if (tl) tl.style.display = active.has("Trace lines") ? "" : "none";
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
document.addEventListener("DOMContentLoaded", main);
