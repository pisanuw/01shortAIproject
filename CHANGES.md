# Changes

Format: `YYYY-MM-DD [type] description` (max 200 chars). Types: decision, plan, doc, scope, code, note.

2026-05-05 [note] Initialized.
2026-05-05 [scope] Added UWB instructor evaluation dashboards from IAS export data (UWB only)
2026-05-05 [code] scripts/build_evals.py: generates per-instructor eval JSON + self-contained HTML; patches professor_index.json for eval-only instructors
2026-05-05 [code] public/app.js: instructor names in dept/course tables are clickable prof links; eval index loaded at startup to show View Evaluations link
2026-05-05 [decision] Eval HTML files are self-contained (data embedded); eval_index.json built from files that exist to prevent dead links
2026-05-05 [decision] Instructor nickname quotes stripped before ID generation so IAS and catalog IDs match (e.g. P.V. 'Sundar' -> P.V. Sundar)
2026-05-05 [note] build_catalog.py overwrites professor_index.json; must run build_evals.py after to restore eval-only instructor entries
2026-05-05 [decision] Eval HTML files use URL-decoded filenames on disk (e.g. Pisan,Yusuf.html) so Python SimpleHTTPRequestHandler can find them after decoding %2C
2026-05-05 [code] Eval dashboard layout: OSR + CEI metric boxes, collapsible details sections (Summative/Student Engagement/Formative), Expand All/Collapse All buttons
2026-05-05 [code] public/styles.css: added .prof-link class for clickable instructor name buttons in table rows
2026-05-05 [note] Full build completed: 496 eval HTML dashboards + 496 JSON files generated; eval_index.json contains 496 encoded instructor IDs
2026-05-05 [scope] Added scripts/find_name_conflicts.py: detects eval-vs-catalog and middle-name-drop mismatches; --apply writes fixes to fixNames.txt
2026-05-05 [code] Applied 284 auto-detected name fixes (60 Rule-1 eval/catalog, 224 Rule-2 middle name); rebuilt with build:all + build:evals
2026-05-05 [note] build:data is legacy Bothell-CSS-only mode; use build:all to regenerate professor/course indexes after fixNames changes
