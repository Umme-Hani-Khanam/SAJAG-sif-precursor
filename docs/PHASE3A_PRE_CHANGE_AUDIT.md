# Phase 3A pre-change audit

Recorded on 2026-08-30 before any Phase 3A implementation changes.

## Verification results

- Backend: `cd backend && pytest -q` completed successfully: **23 passed in 0.94s**.
- Frontend: `cd frontend && npm install && npm run build` completed successfully with Vite 5.4.14: **48 modules transformed; production build succeeded**.
- The Phase 1/2 end-to-end acceptance workflow remains covered by
  `backend/tests/test_alerts_phase2_api.py::test_phase2_acceptance_workflow_end_to_end`
  and passed as part of the full suite.

## Existing schema

The pre-change SQLAlchemy metadata contains these application tables:

- `safety_reports`
- `historical_analyses`
- `hse_reviews`
- `audit_events`
- `capas`
- `capa_evidence`
- `safety_documents`
- `document_chunks`
- `safety_alerts`

Startup currently calls `Base.metadata.create_all()`. There is no migration history,
user/session store, site-scoped identity, background-job store, notification store,
attachment store, or formal validation store.

## Service and flow findings

- Authorization is role-only and is derived from caller-controlled
  `X-Actor-Name` and `X-Actor-Role` headers. There is no login, password hash,
  authenticated session, active-user check, or site scope. The headers therefore
  must be confined to explicit demo mode during Phase 3A.
- Historical batch analysis (`POST /analysis/batch`) runs synchronously in the API
  request. Document ingestion and chunk embedding also run synchronously.
- Knowledge versions are descriptive metadata only. Documents have no lifecycle
  state, approval actor/timestamp, review date, supersession link, retirement, or
  approved/effective-date retrieval filter.
- Uploaded datasets are parsed in memory and persisted as report rows. Uploaded PDF
  reports are read in memory, native text is extracted, and the original file is not
  retained. Scanned/image-only PDFs are rejected.
- Knowledge ingestion persists document metadata, chunk text, and JSON embeddings;
  it does not persist the original uploaded file. Similarity and knowledge retrieval
  load JSON embeddings and compare them in Python, which is suitable for SQLite demo
  data but not an efficient production PostgreSQL vector path.
- Live observations use a generated report `date`; there is no distinct
  `observed_at` versus `submitted_at` provenance.

## Compatibility guardrail

Phase 3A changes will preserve the existing synchronous endpoints and demo behavior
needed by Phase 1/2 tests while adding authenticated, site-scoped, asynchronous, and
governed production paths. Existing user data must not be deleted by migrations.
