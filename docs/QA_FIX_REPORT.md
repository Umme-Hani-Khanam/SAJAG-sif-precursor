# Release-Blocking QA Fix Report

Date: 2026-09-21
Baseline: `466ba4f27350f4fe9138e0952930834b842dbf3d`

## DEF-01 — cluster filter +1 offset

**Root cause.** Persisted DBSCAN cluster IDs are correctly zero-based and backend filters compare those raw IDs directly. The Reports UI displayed one-based `C-{n}` labels in rows but asked users to type a raw numeric “Cluster ID.” Entering the visible suffix from `C-2` therefore submitted internal ID `2`, which is displayed as the next cluster. Label conversion was also duplicated in frontend and backend code.

**Fix.** `cluster_display_label()` is now the authoritative backend mapping. Existing persisted IDs are unchanged. Cluster summaries, live assignment, report responses, detail responses, Emerging Risks, Patterns, Dashboard, Reports, and CSV export consume the backend-owned `cluster_code`. Reports and Dashboard use selectors whose option label comes from `/clusters` and whose value remains the matching raw persisted ID. Noise remains `-1`, is labelled `Unclassified / noise`, and is excluded from established-cluster lists.

**Regression coverage.** `test_cluster_display_mapping_is_consistent_across_filters_details_trends_and_export` proves C-01, C-02, and C-03 each return only their own members across reports, cluster detail, trends, and CSV export. It also verifies noise filtering, labelling, and exclusion from established cluster detail/list semantics.

**Result.** Passed in automated API coverage and manual browser selection of three established clusters.

## DEF-02 — validation CSV schema mismatch

**Root cause.** The backend accepted only the exact canonical header `expected_critical_control`, while the UI documented the field generically as “expected control.” Headers were not normalized and the shared frontend error parser discarded structured error context.

**Fix.** The canonical internal field remains `expected_critical_control`; `expected_control` is accepted only as its documented compatibility alias. The parser strips a BOM, trims header whitespace, safely case-folds headers, fills an empty canonical value from the alias, rejects conflicting non-empty canonical/alias values by CSV row, rejects duplicates after normalization, and returns required columns, aliases, received columns, and missing/conflict details. The UI now shows exact headers, provides a canonical downloadable template, and surfaces structured backend errors.

**Regression coverage.** Tests cover canonical input, the legacy alias, BOM, whitespace/casing normalization, missing control columns, canonical/alias conflicts, persisted canonical values, and a completed validation run with generated metrics.

**Result.** Both schemas passed automated tests and direct acceptance uploads against the running local API; metrics rendered in the Validation page.

## OBS-01 — date filter leaves other dates visible

**Root cause.** Backend filtering was already typed, inclusive, and shared across reports/export/trends. The Reports polling effect captured the initial empty filter closure and reloaded unfiltered rows whenever the latest historical job was completed, while the date controls still appeared active. The table also displayed legacy `Date` even when `observed_at` was the effective filter date. Reports had no Clear action, Dashboard Clear did not re-query, and export used editable rather than applied filters.

**Fix.** Reports now keeps explicit draft and applied filter state plus an applied-filter ref for polling. A completed job refresh occurs once and uses the committed query. Apply, Clear, polling, and CSV export share that committed state. Dashboard Clear sends an empty trends query. Both pages visibly show the active inclusive date range. Report responses expose `effective_event_date` (`observed_at`, otherwise parsed legacy `Date`), and the table/export display it without removing the original Date column.

**Regression coverage.** Endpoint-parity tests cover exact same-day, inclusive multi-day, from-only, to-only, null `observed_at`, timezone-aware `observed_at`, legacy fallback, malformed legacy dates, and identical report/export/trends result counts.

**Result.** Automated parity passed. Manual browser checks returned only 2026-06-10 for an exact-day filter, only 2026-06-10 and 2026-06-12 for the chosen inclusive range, exported exactly those two rows, and Clear restored all 100 reports with empty controls.

## OBS-02 — low-risk housekeeping over-classification

**Investigation outcome.** Reproduced and fixed. Generic fallback extraction assigned “Serious injury” and medium likelihood, and the substring `no ` marked any statement as a missing control—even explicit phrases such as “no critical-control failure.” This produced score 59 / medium for explicit low-energy housekeeping and minor-water-spill observations. Risk thresholds were not the cause.

**Fix.** A narrow deterministic branch recognizes explicit low-energy cardboard-box/walkway housekeeping and minor-water-spill cases, assigning a minor consequence, low likelihood, low-energy slip/trip exposure, and degraded housekeeping control. Broad `no ` matching was replaced with specific control-absence phrases. `not connected` and lost-control phrases were added so genuine fall-protection and toxic-gas failures are not understated.

**Regression coverage.** Two low-energy cases assert the full 5/12/18/2/0 = 37 (Low) breakdown. Work at height, suspended load, LOTO, and toxic gas remain High/Critical with hazardous-energy score 25 and missing controls. Boundary tests preserve Low <40, Medium >=40, High >=70, and Critical >=85.

## Files changed

- `README.md`
- `backend/main.py`
- `backend/models.py`
- `backend/schemas.py`
- `backend/services/clustering.py`
- `backend/services/extraction.py`
- `backend/services/validation.py`
- `backend/tests/test_qa_fixes.py`
- `frontend/src/api/reports.js`
- `frontend/src/components/AnalysisResults.js`
- `frontend/src/components/DashboardPage.js`
- `frontend/src/components/ReportManagement.js`
- `frontend/src/components/ValidationPage.js`
- `frontend/dist/index.html` and its generated hashed JavaScript bundle
- `docs/QA_FIX_PRE_CHANGE_AUDIT.md`
- `docs/QA_FIX_REPORT.md`

`AnalysisResults.js` also received a narrow React correctness cleanup discovered during browser verification: dynamic `ScoreRow` rendering and mapped keys now produce no console warnings.

## Verification result

- Focused QA regression tests: 16 passed.
- Complete backend suite: 64 passed.
- Frontend production build: passed (38 modules).
- `python3 -m compileall backend`: passed.
- `pip check`: no broken requirements.
- Clean temporary SQLite `alembic upgrade head`: passed; `alembic check`: no new upgrade operations.
- `npm audit --audit-level=moderate`: 0 vulnerabilities.
- `git diff --check`: passed; tracked-file secret scan found only the documented `backend/.env.example` and no credential pattern.
- Local browser acceptance: all nine primary pages rendered; text analysis completed; three cluster filters matched exactly; exact/range/Clear/export date flows passed; validation schema/template and stored metrics rendered; no new console warnings after the React cleanup.
- No schema change or data migration is required.
- No environment-variable change is required.

## Production impact and retest

Deploy the new backend and frontend artifacts through the existing Render and Vercel workflows. Do not reseed, truncate, or re-import production data. Existing reports, analyses, cluster IDs, CAPAs, alerts, audits, users, validation history, and knowledge documents remain untouched.

Retest:

1. In Patterns, record three established display codes; select each in Reports and verify every row has that exact code.
2. Confirm noise is shown only as `Unclassified / noise`, never as an established cluster.
3. Apply a same-day date range and then a multi-day range; compare visible effective dates and the exported report IDs; press Clear and verify controls and results reset.
4. Upload one validation CSV using `expected_control` and one using `expected_critical_control`; run evaluation and verify metrics populate.
5. Upload a deliberately conflicting two-control-column CSV and verify the response identifies the CSV row and contract details.
6. Recheck text/photo analysis, report import, historical job status, Patterns, Emerging Risks, CAPA/alerts, Audit, Knowledge governance, Dashboard, authentication/demo behavior, and site scoping.
