# SAJAG — SIF Precursor Intelligence

## Overview

SAJAG is a safety decision-support platform for the SIH26165 problem: identifying Serious Injury and Fatality (SIF) precursor patterns hidden across unsafe-act, unsafe-condition, and near-miss reports. It converts text, PDF, and photo-assisted observations into structured hazard intelligence; applies deterministic SIF scoring; compares historical evidence; groups recurring precursor families; detects new and accelerating risks; and carries findings through human review, corrective action, verified closure, and organizational memory.

SAJAG does **not** predict that a fatality will occur and does not replace an HSE professional. Scores, confidence labels, image findings, and emerging-risk signals support—not automate—safety decisions.

## Features

### Safety intelligence

- Text observations, PDF reports with OCR fallback, and photo-assisted observations.
- Structured extraction of hazard, hazardous energy, exposure, unsafe acts/conditions, critical controls, consequences, likelihood, precursor pattern, and life-saving rule.
- Explainable deterministic SIF score and Low/Medium/High/Critical risk level.
- Weighted historical matching, unique evidence cards, real match percentages, and “Why Flagged” reasons.
- DBSCAN precursor clusters, explicit Unclassified/noise handling, live cluster assignment, new-pattern detection, established-pattern acceleration, trends, and Critical Control Health.
- Evidence provenance separated into Reported by user, Observed in image, and AI inferred.

### Historical data

- CSV/XLSX import and PDF-to-observation intake.
- Persisted batch intelligence, embeddings, cluster assignments, and error status.
- Filtered reports and CSV export using `observed_at` where available.

### Governance and platform

- Authenticated opaque sessions, six roles, and backend-enforced site scopes.
- HSE confirmation/correction while preserving the original AI result.
- Immutable audit events, alerts, CAPA assignment/state/evidence/verification, and recipient-specific notification receipts.
- Governed document RAG with version, effective-date, approval, supersession, retirement, and real source citations.
- Verified corrective-action memory from prior CAPAs.
- Confidence reasons and HSE Review Recommended without changing the SIF risk level.
- Formal labelled validation: precision, recall, F1, false negatives, risk agreement, and critical-control agreement.
- Persisted jobs, evidence attachments, SQLite development support, and PostgreSQL/pgvector-ready migrations/search.

## Roles

| Role | Major permissions |
| --- | --- |
| Worker | Submit observations, view basic results, add CAPA evidence in authorized scope. |
| Site Supervisor | Site-scoped viewing, alert viewing, CAPA assignment/update/evidence. |
| HSE Officer | Review/correct analyses, manage CAPAs and knowledge, verify closure, view audit, decide alerts. |
| HSE Manager | HSE Officer permissions plus advanced analytics across authorized sites. |
| Auditor | Read-only safety, alert, and immutable audit visibility within scope. |
| Admin | All permissions, user creation, unrestricted administration when scope is `*`. |

Every protected backend query and direct entity lookup applies the actor’s site scope. Hiding a UI control is never the authorization boundary.

## Quick start

Python 3.11 or 3.12 and Node.js are recommended.

```bash
git clone https://github.com/Umme-Hani-Khanam/SAJAG-sif-precursor.git
cd SAJAG-sif-precursor/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DEMO_MODE=true
export AUTO_CREATE_SCHEMA=true
alembic upgrade head
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd SAJAG-sif-precursor/frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The API and interactive documentation are at `http://127.0.0.1:8000` and `http://127.0.0.1:8000/docs`.

### Normal authenticated mode

```bash
cd backend
source .venv/bin/activate
export DEMO_MODE=false
export AUTO_CREATE_SCHEMA=false
export DATABASE_URL=sqlite:///./sajag.db
export CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
alembic upgrade head
python3 scripts/create_user.py \
  --name "SAJAG Administrator" \
  --email admin@example.com \
  --username admin \
  --role ADMIN \
  --sites '*'
uvicorn main:app --host 127.0.0.1 --port 8000
```

The user-creation script prompts for a password unless one is explicitly supplied. Do not put production passwords in shell history.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | SAJAG SIF Precursor Intelligence API | API title. |
| `DATABASE_URL` | `sqlite:///./sajag.db` | SQLAlchemy SQLite or PostgreSQL URL. |
| `DEMO_MODE` | `false` | Enables explicit demo identities and actor headers; never production auth. |
| `DEMO_SITE_SCOPE` | `*` | Comma-separated demo-only scope. |
| `AUTO_CREATE_SCHEMA` | true only in demo mode | Calls metadata schema creation; use Alembic outside demos. |
| `CORS_ALLOWED_ORIGINS` | local ports 3000, 5173, 8080 on `localhost` and `127.0.0.1` | Comma-separated exact trusted origins. Wildcard is rejected outside demo mode. |
| `SESSION_TTL_MINUTES` | `60` | Opaque session lifetime, clamped to 5–1440 minutes. |
| `GEMINI_API_KEY` | unset | Optional Gemini text/photo evidence provider key. |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Provider model name. |
| `FORCE_HASHING_EMBEDDINGS` | `false` | Immediately use deterministic 384-dimensional hashing and skip all SentenceTransformer import/download/initialization. Recommended for constrained hosted demos. |
| `UPLOAD_STORAGE_DIR` | `backend/uploads` | Local evidence storage root. |
| `MAX_UPLOAD_BYTES` | `10485760` | Per-upload limit; minimum 1 KiB. |
| `JOB_WORKERS` | `2` | In-process background worker count. |
| `JOB_EXECUTION_MODE` | `thread` | `thread` or deterministic test/demo `eager`. |
| `SIMILAR_RESULTS_LIMIT` | `5` | Maximum historical evidence cards. |
| `SIMILARITY_RESULT_MIN_SCORE` | `0.18` | Minimum combined similarity. |
| `DBSCAN_EPS` | `0.38` | Cosine-distance DBSCAN radius. |
| `DBSCAN_MIN_SAMPLES` | `2` | DBSCAN minimum samples. |
| `CLUSTER_ASSIGNMENT_MIN_SIMILARITY` | `0.58` | Live-to-centroid assignment threshold. |
| `UNCLASSIFIED_RELATED_MIN_SIMILARITY` | `0.56` | Relatedness for unmatched patterns. |
| `PATTERN_CANDIDATE_MIN_COUNT` | `2` | Candidate new-pattern count. |
| `PATTERN_ALERT_MIN_COUNT` | `4` | New-pattern alert count. |
| `PATTERN_ALERT_WINDOW_DAYS` | `30` | New-pattern time window. |
| `EMERGING_CURRENT_WINDOW_DAYS` | `30` | Current/previous trend window. |
| `EMERGING_MIN_CURRENT_COUNT` | `4` | Minimum established-cluster current count. |
| `EMERGING_MIN_GROWTH_RATIO` | `1.0` | Minimum increase ratio (1.0 = 100%). |
| `CONTROL_ACCELERATION_MIN_CURRENT` | `3` | Control-health acceleration count. |
| `CONTROL_ACCELERATION_GROWTH_MULTIPLIER` | `2.0` | Control-health growth multiplier. |

Do not commit `.env` or secrets. Frontend API calls default to `http://127.0.0.1:8000`; append `?api=https://trusted-api.example` to the frontend URL when intentionally selecting another API.

## Demo mode

`DEMO_MODE=true` displays the role selector and permits clearly labelled `X-Actor-Name` / `X-Actor-Role` identities with `DEMO_SITE_SCOPE`. It is convenient for an offline demonstration, but it has no password authentication and must never be internet-exposed. The secure default is `false`; in normal mode those demo headers cannot authenticate and the API requires a valid bearer session.

## Databases and migrations

SQLite is supported for local development and automated tests. PostgreSQL is the production-oriented path and requires pgvector:

```bash
createdb sajag
psql -d sajag -c 'CREATE EXTENSION IF NOT EXISTS vector;'
export DATABASE_URL='postgresql+psycopg://sajag_user:change-me@127.0.0.1:5432/sajag'
cd backend
alembic upgrade head
alembic check
```

Use a real secret manager for the database password. Migration `0001_phase2_baseline` creates the Phase 1/2 schema, `0002_phase3a_platform` adds the Phase 3A platform and pgvector-ready columns/indexes, and `0003_notification_receipts` adds personal notification read receipts. For a legacy pre-Alembic database, back it up and verify it matches the baseline before `alembic stamp 0001_phase2_baseline`; never stamp an unknown schema.

`VectorStore` uses deterministic in-process cosine search on SQLite and PostgreSQL `<=>` nearest-neighbour queries with HNSW indexes on pgvector.

## Historical dataset workflow

1. Open **Reports** and upload CSV/XLSX. Expected columns are `Report ID`, `Date`, `Location/Site`, `Department`, `Activity`, `Report Type`, `Shift`, `Source`, `Company`, `Region`, `Site`, and `Description`.
2. Start **Analyse Historical Dataset**. A persisted job records status and progress while extraction, scoring, embeddings, and clustering run.
3. Inspect progress on Reports, then use **Patterns**, **Emerging Risks**, and **Dashboard**.
4. Filter by site, date, risk, cluster, activity, or control. Date logic prefers `observed_at` and falls back to legacy imported date.
5. Export the current authorized filter set as CSV. A scoped user never receives another site’s rows.

Batch analysis uses the deterministic taxonomy by default. Interactive text extraction may use Gemini when configured; provider failure falls back to deterministic extraction rather than fabricating a response.

## Application user guide

1. **Log in** with a normal account, or choose a labelled demo role only in demo mode.
2. **Load history** on Reports, run batch intelligence, and wait for the persisted job to complete.
3. **Submit an observation** on Analyze using Text, PDF, or Photo and set the actual observation date/time.
4. **Interpret the SIF score** from consequence (30), hazardous energy exposure (25), control failure (25), likelihood (10), and historical recurrence (10). Thresholds: Critical ≥85, High ≥70, Medium ≥40, otherwise Low.
5. **Read Why Flagged** to see evidence-based match components rather than a black-box percentage.
6. **Inspect similar reports**, the assigned cluster or Unclassified status, temporal trend, emerging signal, and governed RAG guidance.
7. **Review patterns and emerging risks** and drill into authorized reports.
8. **Review Critical Control Health** on the Dashboard to see effective, degraded, missing/failed, unknown, high-consequence, accelerated, and affected-site counts.
9. **Perform HSE review** to confirm or correct an analysis. The original AI fields remain preserved for audit and agreement analytics.
10. **Create a CAPA**, assign a responsible supervisor, move it through work states, attach evidence, submit for verification, and let an authorized HSE reviewer close or reopen it.
11. **Inspect Audit** for append-only report, review, alert, CAPA, document, and source-change events.
12. **Govern knowledge** by uploading a Draft, waiting for indexing, approving it, and later superseding or retiring it. Only eligible Approved versions can support new RAG answers.
13. **Run Validation** with a labelled CSV and inspect precision, recall, F1, High/Critical false negatives, risk agreement, and critical-control agreement.
14. **Read notifications** and mark one or all read. Read state belongs to the authenticated recipient, not the shared role/site notification.
15. **Export CSV** from Reports for the current authorized filters.

## Navigation guide

- **Dashboard:** Phase 1/2/3 metrics, risk mix, review/CAPA/alert counts, notifications, and Critical Control Health.
- **Analyze:** text, PDF, and photo intake; structured extraction, score, confidence, provenance, history, pattern, trend, and grounded guidance.
- **Emerging Risks:** established clusters meeting frequency and acceleration evidence thresholds.
- **Patterns:** DBSCAN cluster list, details, report drill-down, exposure/control summaries, and Unclassified noise handling.
- **Reports:** import, batch-job status, filters, report inspection, and CSV export.
- **Actions:** CAPA assignment, state transitions, evidence, verification, and reopening.
- **Audit:** immutable event timeline within authorization scope.
- **Knowledge:** Draft/Approved/Superseded/Retired documents, indexing, approval, source inspection, and RAG eligibility.
- **Validation:** labelled datasets, evaluation runs, quality metrics, and false-negative inspection.

## Photo analysis, PDF/OCR, and provenance

Photo input supports JPEG, PNG, and WEBP within the configured size limit. It separates user text, image-visible findings, and AI inferences; the vision result carries a human-confirmation disclaimer and deterministic SAJAG logic still calculates risk. A missing key or provider failure produces a controlled error rather than invented image findings.

PDF intake attempts native text extraction first. If readable text is insufficient, PyMuPDF renders pages and Tesseract performs OCR. Install the `tesseract` executable (`brew install tesseract` on macOS or `apt install tesseract-ocr` on Debian/Ubuntu). OCR output remains evidence requiring review.

## Grounded RAG and corrective-action memory

Knowledge uploads begin as Draft and are indexed by a background job. Retrieval admits only Approved, effective, non-retired/non-superseded versions as of the observation time. Returned guidance includes stored source metadata and excerpts; it never creates a citation to an absent document. Superseding preserves the prior version as historical evidence. Separately, verified closed CAPAs from related reports can be retrieved as historical corrective-action memory.

## Confidence and validation

Confidence is a rule-based evidence-quality label:

- **HIGH:** strong structured evidence and support.
- **MEDIUM:** usable but incomplete or mixed evidence.
- **LOW:** sparse/ambiguous evidence; HSE review is recommended.

Confidence is not a calibrated probability and never changes SIF risk.

Formal validation compares labelled expected results with a fresh pipeline run. Exact precursor match is TP; mismatch contributes FP and FN. Precision is `TP/(TP+FP)`, recall is `TP/(TP+FN)`, and F1 is their harmonic mean. High/Critical false-negative rate measures expected High/Critical cases predicted below High. Risk exact/adjacent agreement and critical-control agreement are also reported. This is distinct from HSE agreement analytics, which compare operational reviewer corrections with original AI outputs.

## Verification

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python3 -m compileall -q .
pip check
alembic check

cd ../frontend
npm install
npm run build
npm audit --audit-level=moderate
```

The repository does not track `frontend/node_modules`; `npm install` reproduces dependencies from `package-lock.json`. Tailwind, React, and application styling are bundled locally without runtime CDN dependencies.

## Intelligence rules

- Similarity weights: semantic 35%, hazard 15%, energy 10%, exposure 10%, critical control 15%, precursor 15%. Duplicate normalized descriptions are suppressed.
- DBSCAN uses cosine distance; `cluster_id=-1` is always Unclassified/noise.
- An unmatched incident is monitored; 2 related observations become a candidate; 4 within 30 days become an alert by default.
- An established cluster is emerging only with at least 4 current-window reports and at least 100% growth over the previous equal window by default.
- Critical Control Health reports observed effectiveness/failure and acceleration. It is not a control assurance audit by itself.

## Production limitations

- The background executor is in-process and jobs do not survive an API-process crash; use a durable external queue before horizontal scaling.
- Local evidence storage is single-host and lacks object-store durability and malware scanning.
- The migrations and PostgreSQL adapter are implemented, but deployment still requires a real PostgreSQL/pgvector service, backup/restore testing, monitoring, and capacity validation.
- OCR requires a separately installed Tesseract binary; photo analysis requires an approved Gemini configuration.
- Local authentication does not provide enterprise SSO, MFA, login rate limiting, external notification delivery, or SIEM integration.
- Confidence is evidence quality, not a calibrated probability. Formal metrics are meaningful only when the labelled dataset is representative and independently reviewed.
- Production deployment must add HTTPS, secure secret management, hardened object storage, durable jobs, observability, retention policy, disaster recovery, and organization-specific model/rule validation.

## Render hosted-demo recovery

Add this exact Render environment variable, then redeploy:

```text
FORCE_HASHING_EMBEDDINGS=true
```

At startup, SAJAG marks any `queued` or `running` job left by the previous process as failed with `Interrupted by application restart; safe to retry.` Completed jobs and all safety reports are untouched. After the deployment is healthy, open Reports and start **Analyse Historical Dataset** again. Existing pending reports are analysed in place; the upload is not repeated. Progress now reserves 0–80% for extraction, 80–95% for embeddings/vector persistence, and 95–100% for clustering/final commit. Wait for the job to become `completed` and confirm `/analysis/status` reports the expected analysed count.

See [docs/FINAL_AUDIT.md](docs/FINAL_AUDIT.md) and [docs/FINAL_CHANGES_AND_USAGE.md](docs/FINAL_CHANGES_AND_USAGE.md) for the final evidence and full technical handoff.
