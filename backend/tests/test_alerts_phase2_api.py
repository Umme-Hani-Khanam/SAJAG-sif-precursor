from fastapi.testclient import TestClient

import main
from conftest import add_synthetic_reports
from database import get_db
from models import AuditEvent, SafetyAlert
from services.alerts import create_analysis_alerts, decide_alert
from services.pipeline import batch_analyze
from services.roles import Actor
from services.knowledge import ingest_document


def test_alert_acknowledgment_and_escalation_are_audited(db_session):
    report = add_synthetic_reports(db_session)[0]
    batch_analyze(db_session)
    alert = create_analysis_alerts(db_session, report, {"risk_level": "critical", "sif_score": 90, "precursor_pattern": "Fall exposure", "critical_control": "Fall protection", "current_cluster": None, "emerging_risk": None}, Actor("SAJAG", "ADMIN"))[0]
    decide_alert(db_session, alert, Actor("Officer", "HSE_OFFICER"), "acknowledge")
    decide_alert(db_session, alert, Actor("Manager", "HSE_MANAGER"), "escalate", "Multiple sites require management attention.")
    db_session.commit()
    assert alert.status == "escalated"
    types = [event.event_type for event in db_session.query(AuditEvent).filter(AuditEvent.entity_id.in_([report.report_id, alert.alert_id])).all()]
    assert "ALERT_ACKNOWLEDGED" in types and "RISK_ESCALATED" in types


def test_worker_cannot_review_but_hse_officer_can_via_api(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    report = db_session.query(__import__('models').SafetyReport).first()

    def override_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    try:
        worker = client.post(
            f"/reports/{report.report_id}/reviews",
            headers={"X-Actor-Name": "Worker", "X-Actor-Role": "WORKER"},
            json={"decision": "confirmed"},
        )
        officer = client.post(
            f"/reports/{report.report_id}/reviews",
            headers={"X-Actor-Name": "Officer", "X-Actor-Role": "HSE_OFFICER"},
            json={"decision": "confirmed"},
        )
    finally:
        main.app.dependency_overrides.clear()
    assert worker.status_code == 403
    assert officer.status_code == 200


def test_phase2_acceptance_workflow_end_to_end(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    ingest_document(
        db_session,
        Actor("Knowledge Manager", "HSE_MANAGER"),
        {"title": "Approved Lifting Control Standard", "organization": "Test HSE Authority", "version": "2", "source_reference": "AUTH-LIFT-02"},
        "approved-lifting.txt",
        b"For suspended-load work, stop lifting when a person enters the line of fire. Re-establish a barricaded exclusion zone and verify fall protection before work resumes.",
    )
    db_session.commit()

    def override_db():
        yield db_session

    worker_headers = {"X-Actor-Name": "Worker One", "X-Actor-Role": "WORKER"}
    officer_headers = {"X-Actor-Name": "HSE Officer", "X-Actor-Role": "HSE_OFFICER"}
    supervisor_headers = {"X-Actor-Name": "Site Supervisor", "X-Actor-Role": "SITE_SUPERVISOR"}
    manager_headers = {"X-Actor-Name": "HSE Manager", "X-Actor-Role": "HSE_MANAGER"}
    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    observation = "During scaffold material shifting, a worker leaned beyond the guardrail without fall protection while a suspended load moved overhead."
    try:
        first = client.post("/analyze", headers=worker_headers, json={"description": observation, "site": "Plant 2", "activity": "Material shifting"})
        assert first.status_code == 200, first.text
        result = first.json()
        report_id = result["report_id"]
        assert result["grounded_guidance"]["retrieved_sources"][0]["source_reference"] == "AUTH-LIFT-02"
        assert result["role_recommendation"]["role"] == "WORKER"

        review = client.post(
            f"/reports/{report_id}/reviews", headers=officer_headers,
            json={"decision": "corrected", "reviewed_hazard": "Combined fall and suspended-load hazard", "review_note": "Combined hazard confirmed during HSE review."},
        )
        assert review.status_code == 200
        preserved = client.get(f"/reports/{report_id}/reviewed-analysis", headers=officer_headers).json()
        assert preserved["ai_analysis"]["hazard"] != preserved["hse_reviewed_analysis"]["reviewed_hazard"]

        created = client.post(
            "/capas", headers=officer_headers,
            json={"report_id": report_id, "title": "Restore exclusion and fall controls", "description": "Install barricades, assign a banksman, and verify fall protection.", "priority": "critical", "action_type": "corrective"},
        )
        assert created.status_code == 200, created.text
        capa_id = created.json()["capa_id"]
        assert client.post(f"/capas/{capa_id}/assign", headers=officer_headers, json={"owner_name": "Site Supervisor", "owner_role": "SITE_SUPERVISOR"}).status_code == 200
        assert client.post(f"/capas/{capa_id}/status", headers=supervisor_headers, json={"status": "in_progress", "note": "Work started."}).status_code == 200
        assert client.post(f"/capas/{capa_id}/evidence", headers=supervisor_headers, json={"evidence_type": "inspection", "reference": "PHOTO-META-1", "note": "Barricades and banksman verified on site."}).status_code == 200
        assert client.post(f"/capas/{capa_id}/submit-verification", headers=supervisor_headers, json={"note": "Implementation complete."}).status_code == 200
        closed = client.post(f"/capas/{capa_id}/verify", headers=manager_headers, json={"note": "Closure verified during restart inspection."})
        assert closed.status_code == 200 and closed.json()["status"] == "closed"

        later = client.post("/analyze", headers=worker_headers, json={"description": "A worker again leaned outside a scaffold guardrail while a crane load travelled overhead.", "site": "Plant 2", "activity": "Material shifting"})
        assert later.status_code == 200
        assert any(action["capa_id"] == capa_id for action in later.json()["historical_actions"])

        report_audit = client.get(f"/audit?report_id={report_id}", headers=manager_headers)
        assert report_audit.status_code == 200
        event_types = {event["event_type"] for event in report_audit.json()}
        assert {"REPORT_SUBMITTED", "REPORT_ANALYSED", "HSE_REVIEW_CORRECTED"}.issubset(event_types)
    finally:
        main.app.dependency_overrides.clear()
