# Proposals

## 1. Add Parser Test Suite
Goal: prevent regressions when UW page markup changes.

Scope:
- Build fixtures for representative quarter pages.
- Add tests for course header extraction, section extraction, and instructor parsing.
- Add snapshot test for generated schema.

Value:
- Higher confidence when extending quarter range.
- Faster debugging when data looks incomplete.

## 2. Add Data Quality Dashboard
Goal: quickly inspect catalog health after each build.

Scope:
- Generate stats: records per term, unique courses, unique instructors, missing instructors.
- Write output to `data/quality-report.json` and show summary in UI footer.

Value:
- Makes broken downloads or parser drift obvious.

## 3. Improve Filter UX
Goal: make discovery faster for users.

Scope:
- Show result chips for active filters.
- Add one-click remove for each active filter.
- Add optional course-title search box alongside dropdowns.

Value:
- Better usability for large historical datasets.

## 4. Add Download Automation Command Profiles
Goal: simplify authenticated and non-authenticated workflows.

Scope:
- Add npm script examples for common cookie file locations.
- Add a pre-check command that validates cookie file format before download.

Value:
- Fewer setup mistakes for new contributors.

## 5. Deployment Hardening for Netlify
Goal: make deploys reproducible and data-current.

Scope:
- Add `netlify.toml` with explicit publish dir and build command.
- Optionally generate dataset during build if cookies/raw files are present.

Value:
- More consistent production deploy behavior.

## 6. Add API Mode (Optional)
Goal: allow reuse by other clients.

Scope:
- Add lightweight server endpoint that serves filtered query results.
- Keep static UI but make data available to other tools.

Value:
- Enables integrations (chatbot, advisor tools, analytics).
