# UW Course & Professor Finder

## Project Metadata

* GitHub Repository: <https://github.com/pisanuw/01shortAIproject>
* Deployed Site: <https://uwbcssprofs.netlify.app/public/>

## Idea

Build a web app from UW time schedule data so users can quickly answer:

* Which professor taught a specific course?
* Which courses did a specific professor teach?
* When (quarter and year) was the course offered?

The app supports all three UW campuses — **Bothell**, **Tacoma**, and **Seattle** — with a
drill-down UI: select campus → select department → filter by course, professor, quarter, year.

## Architecture overview

### Data pipeline

```
Index page (per campus/term)
        │  discover_depts()
        ▼
data/depts/{CAMPUS}/{TERM}.json      ← discovered dept list

        │  download_catalog.py
        ▼
data/raw/{CAMPUS}/{TERM}_{dept}.html ← raw HTML per dept per term
data/raw/{TERM}_{stem}.html          ← legacy Bothell CSS only

        │  build_catalog.py
        ▼
data/shards/{CAMPUS}/{dept}.json     ← per-dept shard (new UI)
data/catalog.json                    ← legacy Bothell CSS (backward compat)
data/catalog_index.json              ← campus + dept list for UI
```

### URL patterns (public, no NetID required)

| Campus   | Index page | Per-dept HTML |
|----------|-----------|---------------|
| Bothell  | `uwb.edu/registrar/time/{quarter-slug}-course-offerings` | `washington.edu/students/timeschd/pub/B/{TERM}/{dept}.html` |
| Tacoma   | `washington.edu/students/timeschd/pub/T/{TERM}/` | `washington.edu/students/timeschd/pub/T/{TERM}/{dept}.html` |
| Seattle  | `washington.edu/students/timeschd/pub/{TERM}/` | `washington.edu/students/timeschd/pub/{TERM}/{dept}.html` |

## Project structure

```
public/
  index.html      — 3-step wizard UI (campus → dept → filter)
  app.js          — navigation + filter logic
  styles.css      — styles including campus cards and dept list
scripts/
  terms.py        — term code generation, URL helpers
  download_catalog.py — multi-campus dept discovery + download
  build_catalog.py    — multi-campus shard builder
  admin_server.py     — local static dev server
data/
  catalog.json         — legacy Bothell CSS records
  catalog_index.json   — campus + dept index for multi-campus UI
  depts/{CAMPUS}/      — discovered dept lists per term
  shards/{CAMPUS}/     — per-dept built records
  raw/                 — legacy flat raw files (Bothell CSS)
  raw/{CAMPUS}/        — multi-campus raw HTML
```

## Quick start (multi-campus)

Default term window for downloads/builds is AUT2020 through SPR2026.

### 1. Download data for a campus

```bash
# Bothell (all depts, all terms from AUT2017)
npm run download:bothell

# Tacoma
npm run download:tacoma

# Seattle
npm run download:seattle

# All three campuses
npm run download:all
```

### 2. Build the JSON shards

```bash
npm run build:bothell
npm run build:tacoma
npm run build:seattle
# or:
npm run build:all
```

### 3. Start local server

```bash
npm run dev
# open http://localhost:4173/public/
```

## Quick start (legacy — Bothell CSS only)

```bash
npm run download:data   # downloads Bothell CSS protected pages (may need cookies)
npm run build:data      # writes data/catalog.json
npm run dev
```

## Download with cookie authentication

Some quarters require UW login (NetID). Export browser cookies and pass the file:

```bash
python3 scripts/download_catalog.py --campus B --cookie-file /path/to/uw-cookies.json
```

Supported formats: Netscape `cookies.txt`, JSON export (browser extension).

## Incremental builds

To only rebuild one campus or one dept:

```bash
python3 scripts/build_catalog.py --campus T
python3 scripts/build_catalog.py --campus B --dept css
```

### Add a single future quarter

When a new quarter appears (example: SUM2026), you can include it without changing code:

```bash
python3 scripts/download_catalog.py --campus all --add-term SUM2026
python3 scripts/build_catalog.py --campus all --add-term SUM2026
```

If you want that quarter included by default in every run, add it to
`EXTRA_TERM_CODES` in `scripts/terms.py`.

## Seattle scale note

Seattle has 200+ departments × many quarters. Use `--since`/`--until` to limit:

```bash
python3 scripts/download_catalog.py --campus S --since AUT2023 --until SPR2026
```

## Safety and privacy notes

* Cookie files are sensitive — do not commit them.
* `.gitignore` excludes common cookie file patterns.
* Delete cookie files after use.
* Do not commit GitHub personal access tokens to this repo.

## Netlify deploy

Static site — deploy repo root with publish directory `.`.

```bash
npm run build:all
netlify deploy --prod
```
