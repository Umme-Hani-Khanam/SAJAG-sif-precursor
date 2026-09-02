# SAJAG final completion audit

Date: 2026-08-30

## Hosted historical-analysis recovery addendum — 2026-09-02

Render showed extraction progress at 100/100 while all analysis rows remained pending because the old progress callback counted only reports extracted; SentenceTransformer initialization, embedding generation, vector persistence, clustering, and the final transaction happened afterward without distinct progress or logs. An interrupted in-process worker also left its persisted job marked `running` indefinitely.

The hosted-demo path now supports `FORCE_HASHING_EMBEDDINGS=true`, which immediately chooses the existing deterministic 384-dimensional hashing model before any SentenceTransformer import or initialization. Historical progress uses an explicit 0–80 extraction, 80–95 embedding/persistence, and 95–100 clustering/finalization scale. The data transaction commits before the job atomically receives its result, `completed` status, and 100/100 progress. Startup marks only orphaned `queued`/`running` jobs failed with a safe-retry message; completed jobs and source reports are unchanged. Render-visible logs bracket every post-extraction phase and terminal job outcome.

Regression coverage proves forced hashing cannot invoke SentenceTransformer, vectors are deterministic and 384-dimensional, ordinary MiniLM selection remains unchanged when available, initialization failure falls back, restart recovery preserves completed jobs, pending reports become analysed, phased historical jobs complete with results, and handler failures persist an error. The final suite for this addendum is recorded in the completion report.

This audit covers the complete Phase 1, Phase 2, and Phase 3A working tree. It follows the recorded baselines in `PRE_CHANGE_AUDIT.md`, `PHASE2_PRE_CHANGE_AUDIT.md`, and `PHASE3A_PRE_CHANGE_AUDIT.md`.

## Outcome

SAJAG is a persisted SIF precursor intelligence platform, not a prompt-only Gemini wrapper. Imported and live observations are structured, scored, embedded, clustered, trended, compared with historical evidence, optionally grounded in approved controlled documents, and preserved for HSE review, audit, alert, and CAPA workflows. Gemini is optional for interactive extraction and required only for photo evidence; deterministic extraction, scoring, matching, clustering, and analytics remain application services.

## Verified product capabilities

- CSV/XLSX upsert detects inserted, changed, and unchanged reports. Only inserted/changed/failed rows are analysed unless an authorized caller deliberately requests full reanalysis. Changed source rows clear stale derived values and add an audit event.
- Structured analysis, SIF score, risk, embedding/model, status/error, timestamps, and cluster ID persist in the database. SQLite uses deterministic local cosine search; PostgreSQL uses native pgvector columns, `<=>` nearest-neighbour SQL, and HNSW indexes.
- Historical matches expose overall, semantic, hazard, energy, exposure, critical-control, and precursor contributions plus readable reasons. Results are deterministic and duplicate normalized descriptions are suppressed.
- Deterministic cosine DBSCAN persists established cluster IDs. Cluster summaries/drilldown include name, count, sites, activities, hazard, exposure, critical control, precursor, average score, High/Critical counts, and first/last dates. `-1` is unclassified/noise.
- Pattern staging requires related evidence: monitor, candidate, then thresholded new-pattern alert. Established emerging patterns expose 7/30/previous-30/90-day evidence and never claim a fatality prediction.
- Trends, dashboard metrics, critical-control health, filters, and cluster dates use `observed_at` first and the legacy imported date only as fallback.
- AI analysis remains immutable. HSE Confirmed/Corrected/Rejected/Needs More Information decisions are separate records with AI snapshots and append-only audit history.
- CAPA transitions are controlled: Open → Assigned → In Progress → Awaiting Verification → Closed, and Closed → Reopened. Closure requires authorized independent verification and a note. Evidence and attachments are retained.
- Authentication uses salted scrypt hashes and opaque expiring bearer sessions whose SHA-256 digests alone are stored. Inactive, expired, invalid, and revoked sessions are rejected. Secure normal mode is the default; demo headers work only when `DEMO_MODE=true`.
- Backend role and site checks protect direct reports, lists, exports, analytics, jobs, reviews, audit records, alerts, CAPAs, and attachments. Unscoped jobs/CAPAs are not exposed to unrelated site-scoped users.
- Notifications persist, deduplicate, target users/roles/sites, and now store per-reader receipts so one role recipient cannot mark a peer's notification read.
- Controlled documents retain Draft/Approved/Superseded/Retired lifecycle, effective/review dates, approval metadata, version lineage, original attachments, chunks, indexing state, and citations. New RAG excludes non-approved and temporally ineligible versions.
- Upload handling enforces endpoint-specific extensions, declared MIME types, signatures where applicable, byte limits, sanitized display filenames, generated storage keys, and root containment. Storage keys and unsafe parser errors are not returned.
- Native PDF extraction falls back to Tesseract OCR when needed and refuses unusable text. Photo findings distinguish reported, visible, and inferred evidence and require HSE confirmation; provider failure never fabricates results.
- Formal labelled validation is isolated from operational HSE agreement and stores reproducible runs, versions, confusion matrices, precision/recall/F1, risk agreement, control agreement, and High/Critical false-negative metrics.
- The frontend provides secure login, role/site identity, dashboard, text/PDF/photo analysis, evidence and confidence, patterns, emerging risks, reports/export/review, CAPA/alerts, audit, governed knowledge, validation, jobs, and personal notifications. All primary pages passed a browser navigation/console audit.

## Repairs found during the final audit

| Problem | Impact | Fix | Verification |
| --- | --- | --- | --- |
| Validation effect returned a Promise | React treated it as cleanup and the page crashed. | Moved async work into an effect callback with a valid cleanup contract. | Validation rendered in the nine-page browser audit; acceptance and API tests pass. |
| React lists lacked stable keys | Console warnings and fragile reconciliation. | Added entity-based keys across headers, analysis, patterns, reports, actions, and knowledge. | Browser error console is empty. |
| Filters and windows used legacy report `date` | Back-dated/submitted observations distorted clusters, filters, and acceleration. | Prefer `observed_at`, fall back only for legacy rows, and pass live observation time to window calculations. | Regression tests assert date filtering and cluster dates; trend acceptance passes. |
| Role/site notification rows shared one `read_at` | One recipient could silently mark a peer's notification read. | Added `notification_reads`, personal reader keys, per-actor queries, and migration `0003`. | Tests prove peer isolation, mark-one, and mark-all behavior. |
| Site-less jobs/CAPAs/alerts were overexposed | Scoped users could see resources without an authorized site relationship. | Restrict site-less jobs to owner/unrestricted actors and deny or validate site-less governance resources for scoped actors. | Direct cross-user/cross-site regression tests pass. |
| Changed reports retained native vector data | Reanalysis could search stale pgvector embeddings. | Clear serialized and native embeddings when source content changes. | Source-update and vector adapter tests pass. |
| Source mutations were under-audited and parser errors surfaced internals | Weaker provenance and potential internal-detail leakage. | Added `REPORT_SOURCE_UPDATED` and sanitized controlled parser failures. | Audit/security acceptance tests and secret/error review pass. |
| Runtime Tailwind/ESM CDNs and tracked dependencies | Deployment depended on public CDNs and the repository carried generated packages. | Bundled React/Tailwind/PostCSS/Vite locally; removed tracked `node_modules`; retained the lockfile. | Production build passes and `npm audit` reports zero vulnerabilities. |
| Local `127.0.0.1:5173` CORS/preflight path was not conclusively covered, and stale normal-mode UI state could send demo headers | Local authenticated requests could surface a CORS failure before reaching normal 401/login behavior. | Safe defaults explicitly include both `127.0.0.1:5173` and `localhost:5173`; normal mode no longer sends actor-demo headers; configured origins remain exact and wildcard is rejected outside demo mode. | Two parametrized OPTIONS regressions assert origin, credentials, and Authorization headers. Fresh real browser tabs on both origins render login; a 127-origin invalid login reaches the API and returns the expected message with zero console errors. |
| Secure mode was not the default | An omitted setting could unintentionally expose demo identities. | Defaulted `DEMO_MODE` to false and made demo setup explicit. | Normal-mode login, demo-header rejection, inactive/expired/revoked session tests pass. |
| Critical-control and cluster UI omitted useful backend evidence | Operators could not see all supporting context. | Exposed effectiveness/failure/unknown, High/Critical, acceleration, affected-site, exposure, activity, precursor, and control summaries. | All primary pages rendered and relevant API/acceptance tests pass. |

## Final verification evidence

- Backend: `pytest -q` — **44 passed** (including both local-origin CORS regressions).
- Python: `python3 -m compileall -q .` — passed.
- Clean SQLite migration: `alembic upgrade head` applied `0001`, `0002`, and `0003`.
- Schema drift: `alembic check` — **No new upgrade operations detected**.
- Frontend: Vite 8.2.2 production build — **38 modules transformed**, build passed.
- Dependency advisory check: `npm audit --audit-level=moderate` — **0 vulnerabilities**.
- Browser: Dashboard, Analyze, Emerging Risks, Patterns, Reports, Actions, Audit, Knowledge, and Validation all rendered; no console errors. Normal mode rendered secure login from both `127.0.0.1:5173` and `localhost:5173`; a real invalid-login request from the 127 origin returned the expected rejection without a CORS/runtime error. Locally bundled Tailwind computed styles were present. Valid login, identity/role/site scope, and direct cross-site denial are covered by the authenticated acceptance suite; browser automation intentionally did not type the temporary audit password.
- Integrated acceptance tests cover authenticated roles/sites, document governance/RAG, photo provenance, historical similarity/clustering/trends, notifications, reviews/audit, CAPA/evidence/verification, OCR, supersession, and formal validation.

## Deliberate deployment boundaries

- The default executor is an in-process thread pool. Jobs persist and expose failure/progress, but running work does not survive an API-process crash. Deployments needing durable execution must provide a queue-backed `JobExecutor`.
- `LocalFileStorage` is secure for one host, not shared across replicas. Multi-instance deployments should provide object storage, backup, malware scanning, and retention policy.
- PostgreSQL/pgvector adapters and migrations are implemented and migration SQL is tested; this completion environment did not provide a live PostgreSQL server for an external integration run.
- OCR requires the system Tesseract executable. Photo analysis requires configured Gemini credentials and provider availability. Controlled failures are intentional when either dependency is absent.
- Authentication is application-local. Enterprise SSO, MFA, rate limiting, SIEM forwarding, email/SMS delivery, and malware scanning are operational integrations, not silently simulated features.
- Confidence labels are evidence sufficiency signals, not calibrated probabilities and not substitutes for formal validation. SAJAG is decision support and does not predict fatalities with certainty.

## Recommended next production work

Before a multi-site production rollout: add durable queue/object-storage adapters, SSO/MFA and rate limiting at the identity/gateway layer, live PostgreSQL load and failover tests, centralized observability/backup/retention, file malware scanning, and a larger curated validation dataset with signed HSE governance.
