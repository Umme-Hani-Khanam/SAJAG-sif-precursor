# QA Fix Pre-Change Audit

Date: 2026-09-21
Baseline commit: `466ba4f27350f4fe9138e0952930834b842dbf3d`

## Baseline verification

- `git pull --ff-only origin main`: already up to date.
- Working tree: clean; `main` matched `origin/main`.
- Python: 3.14.2.
- Node: v24.11.1; npm: 11.6.2.
- `pytest -q`: 48 passed.
- `npm install`: dependencies already current.
- `npm run build`: passed (Vite 8.2.2, 38 modules transformed).
- `python3 -m compileall -q backend`: passed.
- `git diff --check`: passed.
- `pip check`: no broken requirements.
- `npm audit --audit-level=moderate`: 0 vulnerabilities.
- Clean temporary SQLite migration check: revisions 0001, 0002, and 0003 upgraded successfully; `alembic check` reported no new upgrade operations.

No production database was accessed or modified during this audit.

## DEF-01: cluster filter selects the next cluster

### Reproduction and trace

`HistoricalAnalysis.cluster_id` and the backend `cluster_id` query parameters use the same zero-based persisted value. DBSCAN assigns established labels beginning at `0`; `/reports?cluster_id=`, `/analytics/trends?cluster_id=`, and cluster detail compare that raw value directly. The cluster summary API independently converts it to a one-based display code with `C-{cluster_id + 1}`.

The Patterns page preserves the raw ID as its click value, but the Reports page presents a free-form numeric input labelled **Cluster ID** while report rows show a one-based `C-{n}` label. A user who sees `C-2` and enters `2` submits persisted `cluster_id=2`, whose display label is the next cluster (`C-3`). This reproduces the consistent +1 error. The Dashboard also duplicates the display conversion locally, so there is no single authoritative display mapping.

### Root cause

The defect is a frontend display/query contract error: a human one-based label was paired with a raw zero-based numeric input, while display conversion was duplicated in several places. The persisted IDs and backend equality filter are correct and must not be renumbered.

## DEF-02: validation CSV contract mismatch

### Reproduction and trace

The backend requires the exact header `expected_critical_control` from `GROUND_TRUTH_COLUMNS` and checks pandas column names without BOM removal, trimming, casing normalization, or aliases. The QA header `expected_control` therefore produces a missing-column response even though the Validation page describes the field only as “expected control.” Structured error fields are also discarded by the shared frontend response parser.

### Root cause

The public frontend wording and backend parser expose different schemas, and the parser lacks the requested compatibility/normalization layer. The canonical persisted model and validation metric field are already `expected_critical_control`; no schema migration is required.

## OBS-01: date-filtered rows reappear or appear inconsistent

### Reproduction and trace

The backend path already uses typed `date` values, inclusive comparisons, and the required precedence (`observed_at`, then legacy `Date`) through `report_event_date`. Reports, CSV export, and trends share `filtered_analyses`. Existing coverage confirms `observed_at` overrides a conflicting legacy date.

The release-blocking behavior is reproducible in the Reports UI state flow. Its polling effect captures the initial unfiltered `load()` closure. Every poll after the latest historical job is completed reloads the unfiltered report set while the date controls remain populated, so out-of-range rows reappear under an apparently active filter. The table compounds the ambiguity by displaying the legacy `Date` value even when filtering by `observed_at`. There is no Reports Clear action, and Dashboard Clear resets controls without sending an empty query, leaving filtered backend-derived trend data visible. Export uses editable controls rather than the filters that produced the displayed rows.

### Root cause

Stale/uncommitted frontend filter state, an interval callback pinned to the initial empty query, and display of a different date field from the effective filtered date. Backend date semantics are sound but need full edge-case and endpoint-parity regression coverage.

## OBS-02: possible low-risk housekeeping over-classification

### Controlled reproduction

Two explicitly low-energy observations were classified as a generic serious-injury hazard with a missing critical control and medium likelihood:

- Cardboard box in a walkway with explicit absence of hazardous energy/control failure: score 59, medium.
- Minor water spill near an office sink with explicit absence of hazardous energy/serious injury potential: score 59, medium.

The breakdown for each was consequence 20, energy 8, control failure 25, and likelihood 6. The broad substring rule treats any `"no "` as a missing critical control, while the fallback extraction always assigns serious injury and medium likelihood.

High-energy controls also showed a related precision gap: “fall-arrest system was not connected” was not recognized as a missing control and produced medium (67), while a suspended-load failure and LOTO failure remained critical (86) and toxic-gas loss remained high (71).

### Root cause and constrained correction

OBS-02 is reproduced. The cause is not the documented risk thresholds; it is overly broad negation handling plus an overly severe generic fallback for recognizable minor housekeeping/surface-condition scenarios. The correction will be limited to explicit low-energy housekeeping/minor-spill extraction and precise control-failure phrases. Thresholds remain unchanged: critical >= 85, high >= 70, medium >= 40, low < 40.

## Change constraints confirmed

- Persisted cluster IDs will not be renumbered.
- No destructive migration or production-data operation is needed.
- Existing authentication, CAPA, audit, RAG, photo/OCR, vector, deployment, and hosted-demo behavior remains in scope for regression testing.
