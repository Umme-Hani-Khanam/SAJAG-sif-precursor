from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from database import get_db
from models import SafetyDocument, SafetyReport
from services.auth import create_user
from services.pipeline import batch_analyze
from services.roles import Actor


def _report(report_id, description, site="Site A", date="2026-08-01"):
    from models import HistoricalAnalysis
    item = SafetyReport(
        report_id=report_id, date=date, location_site=site, department="Operations",
        activity="Pipe lifting", report_type="Near miss", shift="Day", source="Acceptance fixture",
        company="SAJAG", region="South", site=site, description=description,
    )
    item.analysis = HistoricalAnalysis(status="pending")
    return item


def test_phase3a_complete_acceptance_workflow(db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("JOB_EXECUTION_MODE", "eager")
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", str(tmp_path))

    create_user(db_session, name="Worker A", email="worker@example.test", username="worker-a", password="worker-password", role="WORKER", site_scope=["Site A"])
    create_user(db_session, name="Supervisor A", email="supervisor@example.test", username="supervisor-a", password="supervisor-password", role="SITE_SUPERVISOR", site_scope=["Site A"])
    create_user(db_session, name="HSE Officer A", email="officer@example.test", username="officer-a", password="officer-password", role="HSE_OFFICER", site_scope=["Site A"])
    create_user(db_session, name="HSE Manager", email="manager@example.test", username="manager", password="manager-password", role="HSE_MANAGER", site_scope=["*"])
    db_session.add_all([
        _report("A-LIFT-1", "A rigger stood below a suspended pipe while the crane slewed and the exclusion barricade was missing.", date="2026-07-20"),
        _report("A-LIFT-2", "A worker entered the lifting exclusion zone beneath a suspended pipe spool during crane handling.", date="2026-07-25"),
        _report("A-LIFT-3", "A tag-line handler moved into the line of fire below an overhead suspended load.", date="2026-08-01"),
        _report("B-SECRET", "Restricted Site B safety report.", site="Site B"),
    ])
    db_session.commit()
    batch_analyze(db_session, actor=Actor("System", "ADMIN"))

    def override_db():
        yield db_session
    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)

    def login(username, password):
        response = client.post("/auth/login", json={"identifier": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    try:
        worker = login("worker-a", "worker-password")
        supervisor = login("supervisor-a", "supervisor-password")
        officer = login("officer-a", "officer-password")
        manager = login("manager", "manager-password")

        # Backend denial is independent of React.
        assert client.get("/reports/B-SECRET", headers=worker).status_code == 403

        # Draft -> indexed -> approved controlled source.
        source = (
            b"For lifting operations, establish and maintain an exclusion zone. "
            b"No worker may stand below a suspended load. Stop work if the barricade is absent."
        )
        upload_v1 = client.post(
            "/knowledge/documents", headers=manager,
            data={"title": "Lifting Safety Standard", "organization": "SAJAG HSE", "version": "1", "effective_date": "2026-01-01", "source_reference": "LIFT-001"},
            files={"file": ("lifting-v1.txt", source, "text/plain")},
        )
        assert upload_v1.status_code == 202, upload_v1.text
        v1 = upload_v1.json()["document"]
        assert v1["status"] == "DRAFT" and upload_v1.json()["job"]["status"] == "completed"
        assert client.post(f"/knowledge/documents/{v1['document_id']}/approve", headers=manager).json()["status"] == "APPROVED"

        monkeypatch.setattr(main, "analyze_photo", lambda *_args, **_kwargs: {
            "visible_hazards": ["Worker positioned below suspended load"],
            "visible_controls": ["Crane lifting equipment visible"],
            "possible_missing_controls": ["No obvious exclusion-zone barricade visible"],
            "possible_exposures": ["Line-of-fire exposure"],
            "image_summary": "A worker is near a suspended pipe during lifting.",
            "confidence": "MEDIUM", "disclaimer": "Image-derived findings require HSE confirmation.",
        })
        photo = client.post(
            "/analyze/photo", headers=worker,
            data={"description": "Worker entered lifting zone during pipe handling.", "site": "Site A", "activity": "Pipe lifting", "observed_at": "2026-08-20T10:00:00+00:00"},
            files={"file": ("hazard.png", b"\x89PNG\r\n\x1a\nacceptance-photo", "image/png")},
        )
        assert photo.status_code == 200, photo.text
        result = photo.json()
        assert result["photo_findings"]["visible_hazards"]
        assert result["input_provenance"]["REPORTED_BY_USER"]
        assert result["input_provenance"]["OBSERVED_IN_IMAGE"]
        assert result["input_provenance"]["AI_INFERRED"]
        assert result["score_breakdown"] and result["similar_reports"]
        assert result["current_cluster"] is not None and result["cluster_trend"] is not None
        assert result["grounded_guidance"]["retrieved_sources"][0]["version"] == "1"
        stored = db_session.get(SafetyReport, result["report_id"])
        assert stored.observed_at.date().isoformat() == "2026-08-20" and stored.submitted_at is not None
        assert result["confidence"]["label"] in {"HIGH", "MEDIUM", "LOW"}

        officer_notifications = client.get("/notifications?unread=true", headers=officer).json()
        assert any(item["entity_id"] == result["report_id"] for item in officer_notifications)
        review = client.post(
            f"/reports/{result['report_id']}/reviews", headers=officer,
            json={"decision": "confirmed", "review_note": "Visual evidence confirmed during HSE review."},
        )
        assert review.status_code == 200
        audit = client.get(f"/audit?report_id={result['report_id']}", headers=officer).json()
        assert any(item["event_type"] == "HSE_REVIEW_CONFIRMED" for item in audit)

        capa_response = client.post(
            "/capas", headers=officer,
            json={
                "report_id": result["report_id"], "title": "Reinstate lifting exclusion zone",
                "description": "Install and verify barricades before lifting resumes.", "priority": "critical",
                "owner_name": "supervisor-a", "owner_role": "SITE_SUPERVISOR",
            },
        )
        assert capa_response.status_code == 200, capa_response.text
        capa = capa_response.json()
        assert any(item["entity_id"] == capa["capa_id"] for item in client.get("/notifications", headers=supervisor).json())
        evidence = client.post(
            f"/capas/{capa['capa_id']}/evidence/upload", headers=supervisor,
            data={"note": "Barricade installation photographed."},
            files={"file": ("closure.png", b"\x89PNG\r\n\x1a\nclosure-photo", "image/png")},
        )
        assert evidence.status_code == 200 and evidence.json()["evidence"]["attachment_id"]
        assert client.post(f"/capas/{capa['capa_id']}/status", headers=supervisor, json={"status": "in_progress", "note": "Work started"}).status_code == 200
        assert client.post(f"/capas/{capa['capa_id']}/submit-verification", headers=supervisor, json={"note": "Barricade verified on site"}).status_code == 200
        assert client.post(f"/capas/{capa['capa_id']}/verify", headers=officer, json={"note": "Independent HSE verification complete"}).json()["status"] == "closed"

        monkeypatch.setattr(main, "extract_pdf_with_fallback", lambda _content: {
            "text": "Scanned observation shows a worker below a suspended load without an exclusion barricade during pipe lifting.",
            "text_source": "ocr", "ocr_confidence": 0.86,
        })
        scanned = client.post(
            "/reports/upload-pdf", headers=worker,
            data={"site": "Site A", "activity": "Pipe lifting", "observed_at": "2026-08-21T09:00:00+00:00"},
            files={"file": ("scanned.pdf", b"%PDF-1.4 acceptance", "application/pdf")},
        )
        assert scanned.status_code == 200 and scanned.json()["document_extraction"]["text_source"] == "ocr"

        upload_v2 = client.post(
            "/knowledge/documents", headers=manager,
            data={"title": "Lifting Safety Standard", "organization": "SAJAG HSE", "version": "2", "effective_date": "2026-08-22", "source_reference": "LIFT-002", "supersedes_document_id": v1["document_id"]},
            files={"file": ("lifting-v2.txt", source + b" A spotter is mandatory.", "text/plain")},
        ).json()["document"]
        assert client.post(f"/knowledge/documents/{upload_v2['document_id']}/approve", headers=manager).json()["status"] == "APPROVED"
        old = db_session.get(SafetyDocument, v1["document_id"])
        assert old.status == "SUPERSEDED" and old.chunks  # traceability retained

        csv_data = (
            "description,expected_hazard,expected_exposure,expected_critical_control,expected_precursor,expected_risk_level\n"
            "Worker below suspended load,Suspended load,Line of fire,Exclusion zone,Line of fire exposure,critical\n"
            "Worker at open edge,Fall from height,Fall exposure,Fall protection,Working at height,high\n"
        ).encode()
        dataset = client.post(
            "/validation/datasets", headers=manager, data={"name": "Acceptance labels"},
            files={"file": ("labels.csv", csv_data, "text/csv")},
        )
        assert dataset.status_code == 200, dataset.text
        validation = client.post(f"/validation/datasets/{dataset.json()['dataset_id']}/run", headers=manager)
        assert validation.status_code == 200
        metrics = validation.json()["metrics"]
        assert {"precursor_precision", "precursor_recall", "precursor_f1", "high_critical_false_negatives", "high_critical_false_negative_rate"}.issubset(metrics)
    finally:
        main.app.dependency_overrides.clear()
