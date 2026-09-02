# SAJAG final changes and usage handoff

Date: 2026-08-30

## 1. Project purpose

SAJAG addresses SIH26165 by finding recurring and accelerating SIF precursor evidence across safety observations. Its end-to-end model is: **Report → Intelligence → Pattern → Early warning → Human validation → Action → Verified closure → Organizational memory**. It supports HSE decisions; it does not predict fatalities or replace professional judgment.

## 2. Original state

Baseline commit `0185e1e` offered upload and per-request text analysis with MiniLM similarity. It re-embedded history on requests, returned repeated evidence when workbook descriptions were duplicated, discarded DBSCAN labels, and lacked persistent derived intelligence, trends, cluster exploration, export, governance, authentication, audit, CAPA, RAG, photo input, and validation. The exact reproduction is in `PRE_CHANGE_AUDIT.md`.

## 3. Phase 1 changes

Phase 1 added persistent historical analysis and embeddings, deterministic structured extraction and SIF scoring, diversified weighted similarity with reasons, persisted DBSCAN clustering, staged unmatched-pattern detection, established-cluster acceleration, temporal trends, dashboard metrics, report filters, CSV export, batch/status APIs, and the first five-page frontend: Dashboard, Analyze, Emerging Risks, Patterns, and Reports.

## 4. Phase 2 changes

Phase 2 added HSE confirmation/correction with immutable AI snapshots, append-only audit history, deterministic roles, CAPA lifecycle and evidence, governed safety-document RAG with real citations, verified corrective-action memory, critical-control health, actionable alerts, HSE agreement analytics, and Actions/Audit/Knowledge pages.

## 5. Phase 3A changes

Phase 3A added password authentication and expiring opaque sessions, backend site scopes, PostgreSQL/pgvector support, Alembic migrations, persisted background jobs, notifications, governed attachments, PDF OCR fallback, photo evidence analysis/provenance, `observed_at`, confidence/review recommendation, formal labelled validation, secure normal-mode login, and the Validation page.

## 6. Final audit fixes

- Replaced an async Validation `useEffect` return with a safe effect callback.
- Added missing React keys.
- Made filters, trend windows, and cluster dates prefer `observed_at`.
- Added personal notification receipts (`0003`) so shared role/site notifications do not share read state.
- Denied unrelated scoped access to site-less jobs, CAPAs, and alerts.
- Cleared both serialized and native vector values when a source report changes and recorded `REPORT_SOURCE_UPDATED`.
- Prevented parser exception details and storage keys from leaking.
- Made `DEMO_MODE=false` the default.
- Removed runtime CDN dependencies, bundled Tailwind, upgraded Vite/PostCSS, and removed tracked `node_modules`.
- Added both `localhost:5173` and `127.0.0.1:5173` to safe local CORS defaults, retained explicit environment configuration, and stopped unauthenticated normal-mode requests from sending demo headers.

## 7. Complete feature inventory

SAJAG now implements CSV/XLSX history intake, text/PDF/photo observations, native PDF extraction and OCR, structured hazards, deterministic risk, persisted embeddings, similarity explanations, DBSCAN patterns, unmatched-pattern staging, emerging risks, trends, critical-control health, HSE reviews, audit, alerts, CAPAs, attachments, verified corrective memory, document governance/RAG, authentication, roles/sites, notifications, jobs, confidence, formal validation, dashboard reporting, filtering, and CSV export.

## 8. Architecture overview

- **React frontend:** static Vite/Tailwind bundle and API adapters.
- **FastAPI backend:** transport, validation, authentication dependencies, and endpoint authorization.
- **Service layer:** extraction, scoring, similarity, clustering, trends, governance, storage, jobs, and validation.
- **SQLAlchemy persistence:** SQLite locally; PostgreSQL plus pgvector for production-oriented vector search.
- **Optional providers:** Gemini for interactive extraction/photo evidence and Tesseract for OCR. Deterministic core logic remains local.

## 9. Backend services

`alerts`, `audit`, `auth`, `capa`, `clustering`, `confidence`, `config`, `embeddings`, `extraction`, `governance_analytics`, `jobs`, `knowledge`, `notifications`, `ocr`, `photo`, `pipeline`, `recommendations`, `reviews`, `roles`, `scoring`, `similarity`, `storage`, `trends`, `validation`, `vector_store`, and `vector_types` each own one bounded concern. `main.py` composes them and performs endpoint-level scope checks.

## 10. Database tables

| Table/model | Purpose |
| --- | --- |
| `safety_reports` | Source observation, date/provenance/confidence/site metadata. |
| `historical_analyses` | Extraction, score, risk, embeddings, cluster, versions/status. |
| `hse_reviews` | Human decision plus immutable AI and reviewed values. |
| `audit_events` | Append-only actor/entity/event history. |
| `capas`, `capa_evidence` | Corrective-action lifecycle and evidence metadata. |
| `safety_documents`, `document_chunks` | Governed source versions and retrievable chunks. |
| `safety_alerts` | Persistent actionable risk signals and decisions. |
| `users`, `auth_sessions` | Local identities, scrypt hashes, token digests, expiry/revocation. |
| `background_jobs` | Persisted type, scope, progress, result/error, timestamps. |
| `notifications`, `notification_reads`, `notification_preferences` | Targeted messages and per-recipient receipts/preferences. |
| `attachments`, `photo_analyses` | Governed evidence files and image findings. |
| `validation_datasets`, `validation_cases`, `validation_runs` | Labelled cases and reproducible formal metrics. |

## 11. API groups and endpoints

- Auth: `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/users`, `/roles/permissions`.
- Intake/intelligence: `/analyze`, `/analyze/photo`, `/reports/upload`, `/reports/upload-pdf`, `/analysis/batch`, `/analysis/status`.
- Jobs: `/jobs`, `/jobs/{id}`, `/jobs/historical-analysis`, `/jobs/ocr`, `/jobs/photo-analysis`.
- Evidence: `/reports`, `/reports/{id}`, `/reports/export.csv`, `/clusters`, `/clusters/{id}`, `/emerging-risks`, `/analytics/trends`, `/metrics/dashboard`.
- Governance: report reviews, `/audit`, `/capas`, CAPA state/evidence/verify routes, `/alerts`, and alert decisions.
- Knowledge: `/knowledge/documents` plus approve/retire/detail operations.
- Platform: `/attachments`, `/notifications`, `/analytics/critical-controls`, `/analytics/hse-agreement`, `/validation/datasets`, and `/validation/runs`.

Open `/docs` on the running backend for exact payload schemas and response codes.

## 12. Frontend pages

Dashboard combines three-phase metrics, notification state, and control health. Analyze supports all intake modes and evidence. Emerging Risks and Patterns show temporal and cluster evidence. Reports owns import/batch/filter/export. Actions manages CAPA. Audit shows immutable events. Knowledge manages controlled sources. Validation runs labelled evaluations.

## 13. Authentication

Passwords use unique salts and memory-hard scrypt hashes; plaintext is never stored. Login creates a random opaque token and stores only its SHA-256 digest. Sessions expire according to `SESSION_TTL_MINUTES`; inactive users, expired/revoked sessions, invalid tokens, and demo headers outside demo mode are rejected.

## 14. Role matrix

Worker submits/basic view/evidence. Site Supervisor manages authorized-site CAPA work and views alerts. HSE Officer reviews, manages knowledge/CAPA, verifies closure, audits, and decides alerts. HSE Manager adds advanced analytics. Auditor has read/audit visibility. Admin has `*` permission. Exact permissions are returned by `/roles/permissions`.

## 15. Site authorization

User site scope is stored as a list; `*` is deliberately unrestricted. Lists, direct lookups, exports, dashboards, clusters, jobs, reviews, CAPAs, alerts, audit, attachments, and notifications apply server-side scope. Site-less resources are visible only to their owning authenticated actor or an unrestricted actor where appropriate.

## 16. AI extraction

Interactive text may call configured Gemini with a strict structured schema. Validation, parsing, and controlled deterministic extraction protect the pipeline. Historical batch processing is deterministic. Provider failure does not invent output; supported text analysis falls back to the local taxonomy.

## 17. Risk scoring

The deterministic 100-point score is potential consequence (30), hazardous energy/exposure (25), critical-control failure (25), likelihood (10), and historical recurrence (10). Critical is ≥85, High ≥70, Medium ≥40, otherwise Low. A score breakdown is returned and stored.

## 18. Similarity algorithm and weights

Candidate score = semantic cosine 35% + hazard 15% + hazardous energy 10% + exposure 10% + critical control 15% + precursor 15%. Stored compatible embeddings are reused. Results below the configured threshold are removed, normalized duplicate descriptions are suppressed, and each card provides component scores and human-readable reasons.

## 19. DBSCAN clustering

Historical compatible embeddings are normalized and clustered by cosine-distance DBSCAN (`eps=0.38`, `min_samples=2` by default). Non-noise labels are persisted deterministically. `-1` remains Unclassified; it is never presented as a real cluster. A live observation joins the nearest centroid only at or above the configured threshold.

## 20. New-pattern logic

Unclassified observations use a separate relatedness threshold. Default stages are monitor at one, candidate at two, and new-pattern alert at four related observations inside 30 days. Counts include the submitted observation and expose evidence; the system does not claim fatality prediction.

## 21. Emerging-risk logic

An established cluster is emerging only if its current window has at least four observations and growth versus the previous equal window is at least 100% by default. The API exposes 7/30/previous-30/90-day counts, delta, ratio, dates, sites, controls, and report evidence.

## 22. Trend logic

Trend services use `observed_at`, falling back to legacy source date. They return period series and cluster acceleration around an explicit observation-time anchor so back-dated reports do not distort “current” evidence.

## 23. Critical Control Health

Controls are aggregated into effective, degraded, missing/failed/bypassed, and unknown states, with High/Critical counts, current/previous periods, acceleration, and affected sites. It is an evidence dashboard, not a replacement for field control assurance.

## 24. HSE review

Authorized reviewers Confirm, Correct, Reject, or request more information. The record snapshots all original AI fields and stores reviewed fields separately. Reviewed values drive reviewed-analysis views without destroying the original result.

## 25. Audit

Audit events are append-only at the application model layer and capture actor, role, event, entity/report/site, timestamp, and structured details. Site authorization applies to audit queries.

## 26. CAPA

The controlled path is Open → Assigned → In Progress → Awaiting Verification → Closed, with Closed → Reopened. Evidence can be attached throughout allowed states. Closure requires an authorized independent verifier and verification note. Due dates and overdue/priority metrics feed dashboards.

## 27. RAG

Retrieval searches chunks from eligible Approved documents only, filtered by effective date and version state. Responses include source IDs, titles, versions, references, and real excerpts. No document means no fabricated citation.

## 28. Corrective-action memory

Related historical reports can supply actions only from verified closed CAPAs. This keeps organizational memory tied to real evidence and completed human workflow.

## 29. Document governance

Upload always creates Draft and an indexing job. Authorized HSE/Admin users approve indexed content. A replacement may supersede a prior version; superseded and retired documents remain historical but are excluded from new RAG. Effective dates are evaluated against the observation time.

## 30. Alerts

Persistent alerts are created from critical reports and qualifying emerging/new patterns. Authorized users can acknowledge, escalate, or dismiss them; decisions and notes are audited.

## 31. Notifications

Notifications deduplicate by key and can target a user, role, and/or site. `notification_reads` records one receipt per actor, so one HSE Officer cannot mark a peer’s notification read. APIs expose list, unread count, mark one, and mark all.

## 32. Photo analysis

JPEG/PNG/WEBP evidence is size/type/signature checked and stored using a generated key. Findings separate user-reported context, image-observed evidence, and AI inference. Image findings require HSE confirmation; absence of a provider returns a controlled error.

## 33. OCR

PDF processing attempts native extraction, then renders pages with PyMuPDF and invokes Tesseract when text is insufficient. Unusable scans fail explicitly. Tesseract is a required system dependency only for the fallback path.

## 34. Attachments

Uploads have endpoint-specific extensions/MIME types, byte limits, sanitized display names, generated storage keys, and resolved-root containment. Download enforces entity/site authorization. Production should add malware scanning and shared object storage.

## 35. Jobs

Jobs persist queued/running/completed/failed state, progress, actor/site scope, timestamps, result, and sanitized failure text. The default executor is an in-process thread pool; `eager` is for deterministic tests/demos. Running work does not survive a process crash.

## 36. Confidence

HIGH/MEDIUM/LOW summarizes evidence sufficiency, accompanied by reasons and a review recommendation. It neither changes risk nor represents a calibrated probability.

## 37. Validation metrics

Labelled CSV cases run through the current pipeline and store versions plus per-case results. Metrics include precursor confusion counts, precision, recall, F1, risk exact/adjacent agreement, critical-control agreement, and High/Critical false-negative rate. Formal validation is separate from operational HSE agreement.

## 38. PostgreSQL/pgvector architecture

Migration `0002` enables `vector`, uses 384-dimensional native columns, and creates HNSW cosine indexes. `PostgresVectorStore` orders database-side queries by `<=>`; SQLite stores portable JSON-compatible vectors and computes cosine locally. A deployment must install pgvector before migration.

## 39. Environment variables

All supported variables and defaults are listed in the root `README.md`: application/database, demo/auth/session, CORS, Gemini, storage/upload, jobs, similarity, DBSCAN, unmatched-pattern, emerging-risk, and critical-control acceleration configuration. `FORCE_HASHING_EMBEDDINGS=true` is the constrained hosted-demo switch: it bypasses SentenceTransformer import, download, initialization, and inference and immediately selects the deterministic 384-dimensional hashing model. Secrets must come from environment/secret management, never Git.

## 40. Complete installation procedure

Clone; create/activate `backend/.venv`; install `requirements.txt`; configure environment; run `alembic upgrade head`; create the first normal user with `scripts/create_user.py`; start Uvicorn. In `frontend`, run `npm install` and `npm run dev -- --host 127.0.0.1`. For PostgreSQL, create the database and vector extension first. Exact commands are in `README.md`.

## 41. Complete application usage walkthrough

Login → import history → start batch job → inspect clusters → submit text/PDF/photo observation with `observed_at` → review score/confidence/provenance/similarity/reasons/pattern/trend/RAG → process HSE notification → confirm/correct → create CAPA → assign → add evidence → submit verification → independently close → inspect audit and corrective memory → monitor control health → govern documents → run validation → export authorized CSV.

## 42. Testing procedure

Backend: `pytest -q`, `python3 -m compileall -q .`, `pip check`, clean temporary `alembic upgrade head`, and `alembic check`. Frontend: `npm run build` and `npm audit --audit-level=moderate`. Repository: staged/unstaged `git diff --check`, tracked-file/secret scans, and browser navigation/console/CORS smoke tests.

## 43. Demo scenario

With `DEMO_MODE=true`, load the bundled history and run analysis; submit a suspended-load observation; inspect matches/cluster/trend/guidance; switch to HSE Officer; review it and create CAPA; switch to Site Supervisor to assign/update/add evidence; switch back to HSE to verify closure; then inspect Audit, Knowledge, Validation, and notifications. Demo identities are illustrative and must never be exposed as production authentication.

## 44. Security controls

Scrypt password hashes, opaque token digests, bounded session expiry, inactive/revoked denial, normal-mode demo-header rejection, explicit credentialed CORS origins, backend RBAC/site enforcement, upload size/MIME/signature/name/path controls, sanitized errors, governed RAG eligibility, real citations, append-only audit events, and no committed `.env`/keys are implemented.

## 45. Known limitations

The in-process queue and local filesystem are single-process/single-host components. No enterprise SSO/MFA/rate limiter, external email/SMS notification delivery, SIEM integration, malware scanner, or turnkey deployment exists. A live PostgreSQL service was not available in the completion environment. OCR/Gemini require external dependencies. Confidence is not calibrated probability; production requires representative governed validation and operational hardening.

Persisted queued/running jobs cannot be resumed across a process restart because execution is in-process. Startup therefore marks those orphaned records failed/interrupted and makes retry explicit; completed jobs and source reports are never changed by recovery.

## 46. Future optional enhancements

Without changing the completed Phase 3A scope, a future production program may add a durable queue, shared object storage and antivirus, SSO/MFA, gateway rate limiting, notification delivery, SIEM/observability, retention/backup automation, live PostgreSQL performance/failover tests, and larger signed multi-site validation sets.
