# Incident Console (demo)

A front-end UI for a regional food-safety recall dashboard — the "Incident
console / Regulator view". It reproduces the mockup as a dark, data-dense
single-page console: incident banner, KPI cards, a schematic regional supply
map, investigation-priority cards, retail and facility tables, an event
timeline, and a notification composer.

> **Synthetic demo data.** Store names/locations are real public places; all
> farms, facilities, lots, inventory, illness reports and lab results are
> synthetic. No real outbreak is alleged. The map is schematic.

## Stack

Zero-dependency **vanilla HTML + CSS + JavaScript** — no build step, no
framework, works fully offline. (The sandbox this was built in has no package
registry access, so React/Vite/Tailwind couldn't be installed; the structure
below ports cleanly to React later if desired.)

## Files

| File         | Purpose                                                        |
|--------------|----------------------------------------------------------------|
| `index.html` | Page shell with the section containers                         |
| `styles.css` | Full dark theme (CSS variables, layout, components, responsive)|
| `data.js`    | All synthetic data in one `DATA` object — edit here            |
| `app.js`     | Renders each section from `DATA`; wires up interactivity       |
| `serve.js`   | Tiny Node static server for local preview                      |

## Run it

Open `index.html` in any browser, or serve it locally:

```bash
node serve.js         # then open http://localhost:8099
# or
python3 -m http.server 8099
```

## Interactivity

- **Retailer / Regulator** toggle in the header
- **Map filters** (Stores, Producers, Illness reports, Trace lines) show/hide
  the matching markers and trace lines
- **Investigation**, **banner**, **facility**, and **zoom** buttons show a
  demo toast (no real notices are sent)
- **Notification** checkboxes and the **Send** button update the draft count

## Customize

Everything data-driven lives in `data.js`. Change incident details, KPI
figures, store/producer positions (`x`/`y` are percentages of the map area),
table rows, timeline steps, or notification recipients there, and the UI
re-renders from it.
