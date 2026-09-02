import builtins
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, inspect

import main
from database import get_db
from models import BackgroundJob, HistoricalAnalysis, SafetyDocument, SafetyReport
from services.auth import create_session, create_user
from services import embeddings
from services.confidence import assess_confidence
from services.jobs import INTERRUPTED_MESSAGE, create_job, execute_job, recover_interrupted_jobs
from services.knowledge import ingest_document, retrieve_guidance, transition_document
from services.notifications import create_notification, mark_all_read, mark_read, notification_query, notification_read_at, unread_notification_query
from services.ocr import OCRProvider, extract_pdf_with_fallback
from services.photo import VisionProvider, analyze_photo, combined_description
from services.roles import Actor
from services.storage import LocalFileStorage, sanitize_filename, save_attachment, validate_file
from services.trends import analytics_series, trend_anchor
from services.validation import calculate_metrics
from services.vector_store import PostgresVectorStore, SQLiteVectorStore


def report(report_id, site, *, observed_at=None):
    item = SafetyReport(
        report_id=report_id, date="2020-01-01", location_site=site, department="Operations",
        activity="Lifting", report_type="Observation", shift="Day", source="Test",
        company="Test", region="South", site=site, description="A worker entered a lifting zone.",
        observed_at=observed_at,
    )
    item.analysis = HistoricalAnalysis(status="pending")
    return item


def client_for(db_session):
    def override_db():
        yield db_session
    main.app.dependency_overrides[get_db] = override_db
    return TestClient(main.app)


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://localhost:5173"])
def test_local_vite_origins_pass_authenticated_cors_preflight(db_session, origin):
    client = client_for(db_session)
    try:
        response = client.options(
            "/notifications",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "authorization" in response.headers["access-control-allow-headers"].lower()
    finally:
        main.app.dependency_overrides.clear()


def test_authentication_invalid_inactive_expired_and_production_headers_rejected(db_session, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    user = create_user(
        db_session, name="Site A Supervisor", email="a@example.test", username="site-a",
        password="a-strong-password", role="SITE_SUPERVISOR", site_scope=["Site A"],
    )
    create_user(
        db_session, name="Inactive", email="off@example.test", username="inactive",
        password="another-strong-password", role="WORKER", site_scope=["Site A"], active=False,
    )
    db_session.commit()
    client = client_for(db_session)
    try:
        assert client.get("/reports", headers={"X-Actor-Role": "ADMIN"}).status_code == 401
        assert client.post("/auth/login", json={"identifier": "site-a", "password": "wrong"}).status_code == 401
        assert client.post("/auth/login", json={"identifier": "inactive", "password": "another-strong-password"}).status_code == 403
        login = client.post("/auth/login", json={"identifier": "site-a", "password": "a-strong-password"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["site_scope"] == ["Site A"]
        session = db_session.query(main.AuthSession if hasattr(main, "AuthSession") else __import__("models").AuthSession).first()
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    finally:
        main.app.dependency_overrides.clear()


def test_cross_site_direct_report_access_is_denied(db_session, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    db_session.add_all([report("A-1", "Site A"), report("B-1", "Site B")])
    user = create_user(
        db_session, name="Supervisor", email="supervisor@example.test", username="supervisor",
        password="supervisor-password", role="SITE_SUPERVISOR", site_scope=["Site A"],
    )
    token, _ = create_session(db_session, user)
    db_session.commit()
    client = client_for(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        assert client.get("/reports/B-1", headers=headers).status_code == 403
        rows = client.get("/reports", headers=headers).json()
        assert [row["report_id"] for row in rows] == ["A-1"]
    finally:
        main.app.dependency_overrides.clear()


def test_clean_alembic_upgrade_head(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(main.Path(main.__file__).resolve().parent / "alembic.ini"))
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"users", "auth_sessions", "background_jobs", "notifications", "notification_reads", "attachments", "validation_runs"}.issubset(tables)
    assert {"observed_at", "submitted_at", "confidence_label"}.issubset(
        {column["name"] for column in inspect(create_engine(url)).get_columns("safety_reports")}
    )


def test_sqlite_vector_search_and_postgres_adapter_contract(db_session):
    item = report("V-1", "Site A")
    vector = np.array([1.0, 0.0, 0.0])
    SQLiteVectorStore().persist_report_embedding(item.analysis, vector, "test-vector")
    db_session.add(item); db_session.commit()
    matches = SQLiteVectorStore().search_similar_reports(db_session, vector, "test-vector")
    assert matches[0][1].report_id == "V-1" and matches[0][0] == pytest.approx(1.0)
    assert "<=>" in PostgresVectorStore.REPORT_SEARCH_SQL
    assert "ORDER BY" in PostgresVectorStore.DOCUMENT_SEARCH_SQL
    assert PostgresVectorStore._literal(vector) == "[1,0,0]"


def test_force_hashing_embeddings_never_imports_sentence_transformers_and_is_deterministic(monkeypatch):
    monkeypatch.setenv("FORCE_HASHING_EMBEDDINGS", "true")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise AssertionError("SentenceTransformer must not be imported in forced hashing mode")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    first, first_model = embeddings.encode_texts(["Suspended load exclusion zone"])
    second, second_model = embeddings.encode_texts(["Suspended load exclusion zone"])
    assert first_model == second_model == embeddings.HASHING_EMBEDDING_MODEL
    assert first.shape == second.shape == (1, 384)
    assert np.array_equal(first, second)


def test_default_embedding_path_and_failed_model_initialization_keep_hashing_fallback(monkeypatch):
    monkeypatch.delenv("FORCE_HASHING_EMBEDDINGS", raising=False)

    class AvailableModel:
        def encode(self, values, **_kwargs):
            return np.ones((len(values), 384), dtype=np.float32)

    monkeypatch.setattr(embeddings, "_model", AvailableModel())
    monkeypatch.setattr(embeddings, "_model_unavailable", False)
    vectors, model = embeddings.encode_texts(["default path"])
    assert model == embeddings.MINILM_MODEL
    assert vectors.shape == (1, 384)

    original_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise RuntimeError("model initialization failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(embeddings, "_model", None)
    monkeypatch.setattr(embeddings, "_model_unavailable", False)
    monkeypatch.setattr(builtins, "__import__", failing_import)
    fallback, fallback_model = embeddings.encode_texts(["fallback path"])
    assert fallback_model == embeddings.HASHING_EMBEDDING_MODEL
    assert fallback.shape == (1, 384)
    assert embeddings._model_unavailable is True


def test_restart_recovery_fails_only_orphaned_jobs(db_session):
    actor = Actor("Manager", "HSE_MANAGER", user_id="MANAGER")
    running = create_job(db_session, actor, "HISTORICAL_ANALYSIS")
    queued = create_job(db_session, actor, "OCR_PROCESSING")
    completed = create_job(db_session, actor, "DOCUMENT_INDEXING")
    running.status = "running"
    queued.status = "queued"
    completed.status = "completed"
    completed.result = json.dumps({"done": True})
    db_session.commit()

    assert recover_interrupted_jobs(db_session) == 2
    assert running.status == queued.status == "failed"
    assert running.error == queued.error == INTERRUPTED_MESSAGE
    assert running.completed_at and queued.completed_at
    assert completed.status == "completed"
    assert json.loads(completed.result) == {"done": True}


def test_historical_job_uses_phased_progress_and_completes_pending_report(db_session, monkeypatch):
    monkeypatch.setenv("FORCE_HASHING_EMBEDDINGS", "true")
    item = report("HOSTED-1", "Site A")
    db_session.add(item)
    actor = Actor("Manager", "HSE_MANAGER", user_id="MANAGER", site_scope=("Site A",), authenticated=True)
    job = create_job(db_session, actor, "HISTORICAL_ANALYSIS")
    db_session.commit()
    progress_events = []

    def handler(db, _payload, progress):
        def record_progress(current, total):
            progress_events.append((current, total))
            progress(current, total)

        return main.batch_analyze(
            db, actor=actor, site_scope=actor.site_scope,
            progress_callback=record_progress,
        )

    completed = execute_job(db_session, job, handler)
    db_session.refresh(item.analysis)
    assert item.analysis.status == "analysed"
    assert item.analysis.embedding_model == embeddings.HASHING_EMBEDDING_MODEL
    assert completed.status == "completed"
    assert completed.error is None
    assert completed.progress_current == completed.progress_total == 100
    assert json.loads(completed.result)["analysed"] == 1
    assert progress_events[0] == (0, 100)
    assert progress_events[-1] == (99, 100)
    assert all(total == 100 for _, total in progress_events)
    assert [current for current, _ in progress_events] == sorted(current for current, _ in progress_events)
    assert {80, 88, 95, 99}.issubset({current for current, _ in progress_events})


def test_job_lifecycle_progress_and_failure(db_session):
    actor = Actor("Manager", "HSE_MANAGER")
    success = create_job(db_session, actor, "HISTORICAL_ANALYSIS")
    db_session.commit()
    execute_job(db_session, success, lambda _db, _payload, progress: (progress(2, 4), {"done": True})[1])
    assert success.status == "completed" and success.progress_current == 2 and json.loads(success.result)["done"]
    assert success.started_at and success.completed_at

    failure = create_job(db_session, actor, "HISTORICAL_ANALYSIS")
    db_session.commit()
    execute_job(db_session, failure, lambda *_: (_ for _ in ()).throw(RuntimeError("controlled failure")))
    assert failure.status == "failed" and "controlled failure" in failure.error and failure.completed_at


def test_unscoped_jobs_and_capas_are_not_exposed_to_other_scoped_users(db_session):
    owner = Actor("Owner", "HSE_MANAGER", user_id="OWNER", site_scope=("Site A",), authenticated=True)
    peer = Actor("Peer", "HSE_MANAGER", user_id="PEER", site_scope=("Site A",), authenticated=True)
    job = create_job(db_session, owner, "HISTORICAL_ANALYSIS")
    db_session.commit()
    assert main.list_jobs(db=db_session, actor=owner)[0]["job_id"] == job.job_id
    assert main.list_jobs(db=db_session, actor=peer) == []
    with pytest.raises(HTTPException) as job_denied:
        main.get_job(job.job_id, db=db_session, actor=peer)
    assert job_denied.value.status_code == 403


def test_notification_deduplication_scope_and_read_state(db_session):
    kwargs = dict(
        notification_type="CRITICAL_REPORT", title="Critical report", message="Review now",
        entity_type="REPORT", entity_id="R-1", dedupe_key="critical:R-1",
        recipient_role="HSE_OFFICER", recipient_site="Site A",
    )
    first = create_notification(db_session, **kwargs)
    second = create_notification(db_session, **kwargs)
    db_session.commit()
    assert first.notification_id == second.notification_id
    actor_a = Actor("Officer A", "HSE_OFFICER", user_id="USER-A", site_scope=("Site A",))
    actor_a_peer = Actor("Officer A Peer", "HSE_OFFICER", user_id="USER-A-PEER", site_scope=("Site A",))
    actor_b = Actor("Officer B", "HSE_OFFICER", user_id="USER-B", site_scope=("Site B",))
    assert notification_query(db_session, actor_a).count() == 1
    assert notification_query(db_session, actor_b).count() == 0
    assert unread_notification_query(db_session, actor_a).count() == 1
    assert mark_read(db_session, actor_a, first.notification_id) is first
    assert notification_read_at(db_session, actor_a, first.notification_id) is not None
    assert unread_notification_query(db_session, actor_a).count() == 0
    assert unread_notification_query(db_session, actor_a_peer).count() == 1
    assert mark_all_read(db_session, actor_a_peer) == 1


def test_observed_at_drives_report_filters_and_cluster_dates(db_session):
    item = report("OBS-DATE", "Site A", observed_at=datetime(2026, 8, 29, tzinfo=timezone.utc))
    item.date = "2020-01-01"
    item.analysis.status = "analysed"
    item.analysis.cluster_id = 0
    db_session.add(item); db_session.commit()
    rows = main.filtered_analyses(db_session, date_from="2026-08-01", date_to="2026-08-31")
    assert [row.report_id for row in rows] == ["OBS-DATE"]
    assert __import__("services.clustering", fromlist=["summarize_clusters"]).summarize_clusters(rows)[0]["first_seen"] == "2026-08-29"


def test_document_governance_and_temporal_rag(db_session):
    actor = Actor("Knowledge Manager", "HSE_MANAGER")
    text = b"Before lifting, establish an exclusion zone and prevent workers from standing below a suspended load."
    draft = ingest_document(db_session, actor, {
        "title": "Lifting Standard", "organization": "SAJAG", "version": "1",
        "status": "DRAFT", "effective_date": "2025-01-01",
    }, "lifting.txt", text)
    db_session.commit()
    analysis = {"hazard": "suspended load", "critical_control": "lifting exclusion zone", "precursor_pattern": "line of fire"}
    assert retrieve_guidance(db_session, analysis, observed_at=datetime(2025, 2, 1, tzinfo=timezone.utc))["grounding_status"] == "no_source"
    transition_document(db_session, draft, actor, "APPROVE"); db_session.commit()
    assert retrieve_guidance(db_session, analysis, observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc))["grounding_status"] == "no_source"
    included = retrieve_guidance(db_session, analysis, observed_at=datetime(2025, 2, 1, tzinfo=timezone.utc))
    assert included["grounding_status"] == "grounded"
    assert included["retrieved_sources"][0]["version"] == "1"
    replacement = ingest_document(db_session, actor, {
        "title": "Lifting Standard", "organization": "SAJAG", "version": "2", "status": "DRAFT",
        "effective_date": "2026-01-01", "supersedes_document_id": draft.document_id,
    }, "lifting-v2.txt", text)
    transition_document(db_session, replacement, actor, "APPROVE", supersedes=draft); db_session.commit()
    assert draft.status == "SUPERSEDED" and draft.chunks
    transition_document(db_session, replacement, actor, "RETIRE"); db_session.commit()
    assert retrieve_guidance(db_session, analysis, observed_at=datetime(2027, 1, 1, tzinfo=timezone.utc))["grounding_status"] == "no_source"


class FakeVision(VisionProvider):
    def inspect(self, _content, _media_type, _description=""):
        return {
            "visible_hazards": ["Worker below suspended load"], "visible_controls": ["Crane hook visible"],
            "possible_missing_controls": ["No barricade is visible"], "possible_exposures": ["Line of fire"],
            "image_summary": "A lifting operation with a worker near the load.", "confidence": "medium",
        }


def test_photo_payload_and_provenance_without_fabrication():
    findings = analyze_photo(b"image", "image/png", "Reporter text", provider=FakeVision())
    combined, provenance = combined_description("Worker entered the lifting zone.", findings)
    assert findings["confidence"] == "MEDIUM"
    assert provenance["REPORTED_BY_USER"] == ["Worker entered the lifting zone."]
    assert "Worker below suspended load" in provenance["OBSERVED_IN_IMAGE"]
    assert "No barricade is visible" in provenance["AI_INFERRED"]
    assert "AI inferred possibilities requiring confirmation" in combined


def test_photo_api_runs_existing_pipeline_and_persists_provenance(db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(main, "analyze_photo", lambda *_args, **_kwargs: {
        "visible_hazards": ["Worker below suspended load"], "visible_controls": [],
        "possible_missing_controls": ["Exclusion barricade may be absent"],
        "possible_exposures": ["Line of fire"], "image_summary": "Pipe lifting is visible.",
        "confidence": "MEDIUM", "disclaimer": "Image-derived findings require HSE confirmation.",
    })
    client = client_for(db_session)
    try:
        response = client.post(
            "/analyze/photo",
            data={"description": "Worker entered lifting zone during pipe handling.", "site": "Site A", "activity": "Pipe lifting", "observed_at": "2026-08-20T10:30:00+00:00"},
            files={"file": ("hazard.png", b"\x89PNG\r\n\x1a\nmock-image", "image/png")},
            headers={"X-Actor-Name": "Worker", "X-Actor-Role": "WORKER"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["sif_score"] >= 0 and "score_breakdown" in payload
        assert "similar_reports" in payload and "pattern_status" in payload and "grounded_guidance" in payload
        assert payload["photo_findings"]["visible_hazards"] == ["Worker below suspended load"]
        assert payload["input_provenance"]["REPORTED_BY_USER"] == ["Worker entered lifting zone during pipe handling."]
        assert payload["input_provenance"]["AI_INFERRED"] == ["Exclusion barricade may be absent", "Line of fire"]
        stored = db_session.get(SafetyReport, payload["report_id"])
        assert stored.observed_at.date().isoformat() == "2026-08-20" and stored.submitted_at is not None
        bad = client.post(
            "/analyze/photo", data={"site": "Site A"},
            files={"file": ("hazard.exe", b"not-an-image", "application/octet-stream")},
        )
        assert bad.status_code == 400
    finally:
        main.app.dependency_overrides.clear()


def test_background_job_api_returns_queued_without_blocking(db_session, monkeypatch):
    def persist_only(db, _job):
        db.commit()
    monkeypatch.setattr(main, "submit_persisted_job", persist_only)
    client = client_for(db_session)
    try:
        response = client.post(
            "/jobs/historical-analysis", json={"include_failed": True, "reanalyze_all": False, "use_gemini": False},
            headers={"X-Actor-Name": "Manager", "X-Actor-Role": "HSE_MANAGER"},
        )
        assert response.status_code == 202 and response.json()["status"] == "queued"
        polled = client.get(f"/jobs/{response.json()['job_id']}")
        assert polled.status_code == 200 and polled.json()["status"] == "queued"
    finally:
        main.app.dependency_overrides.clear()


class FakeOCR(OCRProvider):
    def extract_pdf(self, _content):
        return ("Scanned report: worker entered a suspended-load exclusion zone without a barricade during lifting operations. " * 2, 0.88)
    def extract_image(self, _content):
        return ("image text", 0.5)


class EmptyOCR(FakeOCR):
    def extract_pdf(self, _content):
        return ("", None)


def blank_pdf():
    stream = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.write(stream); return stream.getvalue()


def test_ocr_fallback_and_empty_refusal():
    result = extract_pdf_with_fallback(blank_pdf(), provider=FakeOCR())
    assert result["text_source"] == "ocr" and result["ocr_confidence"] == 0.88 and result["text"]
    with pytest.raises(HTTPException) as exc:
        extract_pdf_with_fallback(blank_pdf(), provider=EmptyOCR())
    assert exc.value.status_code == 422


def test_scanned_pdf_api_exposes_ocr_metadata_and_runs_analysis(db_session, monkeypatch):
    monkeypatch.setattr(main, "extract_pdf_with_fallback", lambda _content: {
        "text": "Scanned report: a worker entered the lifting exclusion zone below a suspended pipe while crane handling continued.",
        "text_source": "ocr", "ocr_confidence": 0.91,
    })
    client = client_for(db_session)
    try:
        response = client.post(
            "/reports/upload-pdf", data={"site": "Site A", "activity": "Pipe lifting"},
            files={"file": ("scan.pdf", b"%PDF-1.4 mock", "application/pdf")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["document_extraction"] == {"text_source": "ocr", "ocr_confidence": 0.91}
        assert response.json()["report_id"]
    finally:
        main.app.dependency_overrides.clear()


def test_attachment_security(tmp_path, db_session, monkeypatch):
    storage = LocalFileStorage(tmp_path)
    actor = Actor("Worker", "WORKER")
    item = save_attachment(
        db_session, actor, entity_type="REPORT", entity_id="R-1", filename="../../hazard photo.png",
        media_type="image/png", content=b"\x89PNG\r\n\x1a\ncontent", storage=storage,
    )
    assert item.filename == "hazard photo.png" and "storage_key" not in __import__("services.storage", fromlist=["attachment_to_dict"]).attachment_to_dict(item)
    assert storage.path_for(item.storage_key).parent == tmp_path.resolve()
    with pytest.raises(HTTPException):
        validate_file("photo.png", "image/jpeg", b"\x89PNG\r\n\x1a\ncontent")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    with pytest.raises(HTTPException) as exc:
        validate_file("large.txt", "text/plain", b"x" * 1025)
    assert exc.value.status_code == 413
    with pytest.raises(ValueError):
        storage.path_for("../escape.png")


def test_validation_formulas_false_negatives_and_zero_denominators():
    cases = [
        {"expected_precursor": "line of fire", "predicted_precursor": "line of fire", "expected_risk_level": "critical", "predicted_risk_level": "medium", "expected_critical_control": "barricade", "predicted_critical_control": "barricade"},
        {"expected_precursor": "fall exposure", "predicted_precursor": "other", "expected_risk_level": "high", "predicted_risk_level": "high", "expected_critical_control": "harness", "predicted_critical_control": "guardrail"},
        {"expected_precursor": "loto", "predicted_precursor": "loto", "expected_risk_level": "low", "predicted_risk_level": "low", "expected_critical_control": "isolation", "predicted_critical_control": "isolation"},
    ]
    metrics, matrix = calculate_metrics(cases)
    assert metrics["precursor_precision"] == pytest.approx(2 / 3)
    assert metrics["precursor_recall"] == pytest.approx(2 / 3)
    assert metrics["precursor_f1"] == pytest.approx(2 / 3)
    assert metrics["high_critical_false_negatives"] == 1
    assert metrics["high_critical_false_negative_rate"] == pytest.approx(0.5)
    assert metrics["risk_exact_agreement"] == pytest.approx(2 / 3)
    assert metrics["risk_adjacent_agreement"] == pytest.approx(2 / 3)
    assert matrix["critical"]["medium"] == 1
    empty, _ = calculate_metrics([])
    assert empty["precursor_f1"] == 0 and empty["high_critical_false_negative_rate"] == 0


def test_confidence_labels_reasons_and_review_recommendation():
    weak = assess_confidence(
        description="Worker near crane", site="", activity="",
        analysis={"risk_level": "critical", "critical_control": "Unknown", "similar_reports": []},
        text_source="image", input_quality="LOW",
    )
    assert weak["label"] == "LOW" and weak["reasons"] and weak["hse_review_recommended"] is True
    strong = assess_confidence(
        description="A detailed observation describing a worker entering the controlled lifting exclusion zone while a suspended pipe moved overhead during handling operations.",
        site="Site A", activity="Pipe lifting",
        analysis={"risk_level": "critical", "critical_control": "Exclusion zone", "similar_reports": [{"report_id": "R"}]},
    )
    assert strong["label"] == "HIGH" and strong["hse_review_recommended"] is False


def test_trends_use_observed_at_instead_of_legacy_report_date(db_session):
    recent = report("OBS-1", "Site A", observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    recent.analysis.status = "analysed"; recent.analysis.risk_level = "high"
    old = report("OBS-2", "Site A", observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
    old.analysis.status = "analysed"; old.analysis.risk_level = "low"
    db_session.add_all([recent, old]); db_session.commit()
    items = [recent.analysis, old.analysis]
    assert trend_anchor(items).isoformat() == "2026-08-01"
    assert [point["period"] for point in analytics_series(items)["series"]] == ["2026-07", "2026-08"]
