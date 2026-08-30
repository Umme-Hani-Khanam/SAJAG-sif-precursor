import pytest
from fastapi import HTTPException

from conftest import add_synthetic_reports
from models import AuditEvent, HistoricalAnalysis, SafetyReport
from services.audit import append_audit
from services.pipeline import batch_analyze
from services.reviews import agreement_metrics, create_review
from services.roles import Actor, require


def test_hse_review_persists_without_overwriting_ai_analysis(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    report = db_session.query(SafetyReport).first()
    original_hazard = report.analysis.hazard
    original_control = report.analysis.critical_control
    review = create_review(
        db_session,
        report,
        Actor("Asha HSE", "HSE_OFFICER"),
        {
            "decision": "corrected",
            "reviewed_hazard": "Verified fall from height hazard",
            "review_note": "Site inspection confirmed an exposed platform edge.",
        },
    )
    db_session.commit()

    assert review.review_status == "corrected"
    assert review.ai_hazard == original_hazard
    assert review.reviewed_hazard != original_hazard
    assert report.analysis.hazard == original_hazard
    assert report.analysis.critical_control == original_control
    assert db_session.query(AuditEvent).filter_by(event_type="HSE_REVIEW_CORRECTED", entity_id=report.report_id).count() == 1


def test_role_permissions_are_backend_enforced():
    with pytest.raises(HTTPException) as denied:
        require(Actor("Worker One", "WORKER"), "REVIEW_ANALYSIS")
    assert denied.value.status_code == 403
    require(Actor("HSE One", "HSE_OFFICER"), "REVIEW_ANALYSIS")
    require(Actor("Audit One", "AUDITOR"), "AUDIT_VIEW")


def test_audit_events_are_append_only(db_session):
    event = append_audit(db_session, Actor("Manager", "HSE_MANAGER"), "REPORT_SUBMITTED", "REPORT", "R-1")
    db_session.commit()
    event.reason = "attempted mutation"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    persisted = db_session.get(AuditEvent, event.event_id)
    db_session.delete(persisted)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(AuditEvent, event.event_id) is not None


def test_hse_agreement_metrics_are_not_called_accuracy(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    reports = db_session.query(SafetyReport).limit(3).all()
    create_review(db_session, reports[0], Actor("Officer", "HSE_OFFICER"), {"decision": "confirmed"})
    create_review(db_session, reports[1], Actor("Officer", "HSE_OFFICER"), {"decision": "corrected", "reviewed_precursor": "Corrected precursor", "review_note": "Classification adjusted."})
    create_review(db_session, reports[2], Actor("Officer", "HSE_OFFICER"), {"decision": "rejected", "review_note": "Not a credible SIF precursor."})
    db_session.commit()
    metrics = agreement_metrics(db_session)
    assert metrics["reviewed_reports"] == 3
    assert metrics["hse_agreement_rate"] == 33.3
    assert metrics["correction_rate"] == 33.3
    assert metrics["rejected_flag_rate"] == 33.3
    assert "accuracy" not in metrics
