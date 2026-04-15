# Codebase Review

## Overview
This project is a static web app that helps users explore UW Bothell CSS course offerings by course, quarter, and instructor.

The architecture has two layers:
- Data pipeline (Python): downloads quarter HTML pages and builds a normalized JSON dataset.
- Frontend (HTML/CSS/JS): loads the dataset and provides interactive filtering.

## Main Components

### Frontend
- `public/index.html`: page structure, filter controls, and table output.
- `public/styles.css`: visual layout and responsive styling.
- `public/app.js`: loads `data/catalog.json`, builds dynamic dropdown options, and filters rows.

Key frontend behavior:
- Three intelligent dropdowns (course, quarter, professor).
- Dropdown options update based on current selections.
- Result table updates immediately on filter changes.

### Data Pipeline
- `scripts/terms.py`: defines quarter coverage from AUT2017 to SPR2026.
- `scripts/download_catalog.py`: downloads quarter HTML files into `data/raw/`.
  - Supports unauthenticated and authenticated runs.
  - Cookie input supports Netscape TXT and JSON exports.
- `scripts/build_catalog.py`: parses raw HTML and writes `data/catalog.json`.
  - Extracts course code, course title, section, instructor, and quarter.
  - Uses local raw files when direct fetch is blocked.

### Data Files
- `data/raw/*.html`: source quarter pages.
- `data/catalog.json`: generated structured dataset consumed by frontend.

## Execution Flow
1. Download quarter pages with `npm run download:data`.
2. Build normalized dataset with `npm run build:data`.
3. Start static server with `npm run dev`.
4. Open `/public/` route in browser.

## Strengths
- Clear separation between ingestion and UI.
- No backend dependency for runtime; easy static deployment.
- Good resilience for SSO-protected pages via cookie-based/local-file fallback.
- Dropdown filtering is user-friendly and context-aware.

## Risks and Gaps
- Parser depends on current UW HTML structure; markup changes may require regex updates.
- Missing automated tests for parsing and filtering logic.
- No data freshness indicator beyond generated timestamp/report text.
- No explicit error UI for missing/invalid cookie files in frontend (CLI handles this).

## Recommended Next Improvements
- Add unit tests for parser edge cases and filter logic.
- Add validation script for malformed raw files.
- Add CI workflow to run `build:data` and basic checks on every push.
- Add export options (CSV download of filtered results).
