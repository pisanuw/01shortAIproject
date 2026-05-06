# Briefing

- **Purpose:** UW Courses web app — search UW course offerings by campus, department, professor, or course across Bothell, Seattle, and Tacoma. Instructor evaluation dashboards for UWB faculty.

- **Current scope:**
  - Vanilla JS SPA at `public/index.html` + `public/app.js` with hash-based routing
  - Course data: `data/shards/{B,T,S}/{dept}.json`, indexed via `data/professor_index.json` and `data/course_index.json`
  - Instructor names in course/department tables are clickable links to the professor page
  - Evaluation dashboards: `public/evals/{id}.html` (self-contained HTML per instructor)
  - Eval data source: UWB IAS export files in `data/evals/uwb/natives/0001/`
  - `scripts/build_evals.py` generates eval JSON + HTML and patches `professor_index.json` for eval-only instructors
  - Eval index at `data/evals/eval_index.json` controls which professor pages show the "View Evaluations" link
  - `scripts/find_name_conflicts.py` detects instructor name mismatches (eval vs catalog same section; middle name drop within catalog); `--apply` writes fixes to `fixNames.txt`

- **Key decisions:**
  - Per-file HTML for eval dashboards (self-contained, no runtime fetch of JSON)
  - Eval index is built from files that actually exist (prevents dead links)
  - Eval-only instructors (in IAS but not in time schedule catalog) get professor files derived from eval params; these are never overwritten by `build_catalog.py` unless re-run
  - Instructor nickname quotes (e.g. `'Sundar'`) are stripped from names before ID generation so eval and catalog IDs match
  - `build_catalog.py` will overwrite `professor_index.json`; run `build_evals.py` afterwards to restore eval-only entries
  - After new data: run `build:all` (not `build:data` — that is legacy CSS-only), then `find:conflicts:apply`, then `build:all` again, then `build:evals`
  - Item groupings: Summative (S1,S6,S13,S14, 0-5), Student Engagement (S180-S184, 1-7), Standard Formative (S27-S161, 0-5); excluded: S186-S189, combo

- **Non-goals:**
  - Open-ended student comment text (not in current IAS export)
  - Trend/graph view (deferred)
  - Evaluation data for Seattle or Tacoma campuses (only UWB data available)
