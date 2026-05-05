# Changes

Format: `YYYY-MM-DD [type] description` (max 200 chars). Types: decision, plan, doc, scope, code, note.

2026-05-05 [note] Initialized.
2026-05-05 [scope] Added UWB instructor evaluation dashboards from IAS export data (UWB only)
2026-05-05 [code] scripts/build_evals.py: generates per-instructor eval JSON + self-contained HTML; patches professor_index.json for eval-only instructors
2026-05-05 [code] public/app.js: instructor names in dept/course tables are clickable prof links; eval index loaded at startup to show View Evaluations link
2026-05-05 [decision] Eval HTML files are self-contained (data embedded); eval_index.json built from files that exist to prevent dead links
2026-05-05 [decision] Instructor nickname quotes stripped before ID generation so IAS and catalog IDs match (e.g. P.V. 'Sundar' -> P.V. Sundar)
2026-05-05 [note] build_catalog.py overwrites professor_index.json; must run build_evals.py after to restore eval-only instructor entries
