from conftest import add_synthetic_reports
from models import CAPA, HistoricalAnalysis, SafetyDocument
from services.capa import assign_capa, create_capa, transition_capa, verify_closure
from services.governance_analytics import critical_control_health
from services.knowledge import ingest_document, no_source_guidance, retrieve_guidance
from services.pipeline import batch_analyze
from services.recommendations import historical_corrective_actions
from services.roles import Actor


LIFTING_STANDARD = b"""APPROVED LIFTING SAFETY STANDARD
Line of Fire and Suspended Loads
Before lifting starts, establish a barricaded exclusion zone and appoint a competent banksman. Stop lifting immediately if any person enters beneath a suspended load. Work may restart only after the exclusion zone is restored and the lifting supervisor verifies the control."""


def test_document_ingestion_retrieval_and_real_citation(db_session):
    actor = Actor("HSE Manager", "HSE_MANAGER")
    document = ingest_document(
        db_session, actor,
        {"title": "Approved Lifting Safety Standard", "organization": "SAJAG Test HSE", "version": "1.0", "effective_date": "2026-01-01", "source_reference": "TEST-HSE-LIFT-001"},
        "lifting-standard.txt", LIFTING_STANDARD,
    )
    db_session.commit()
    result = retrieve_guidance(db_session, {"hazard": "Suspended load", "energy_source": "Gravity", "exposure_type": "Line of fire", "critical_control": "Lifting exclusion zone", "precursor_pattern": "Suspended-load exposure", "life_saving_rule": "Stay out of line of fire"})

    assert document.chunk_count >= 1
    assert result["grounding_status"] == "grounded"
    assert result["retrieved_sources"]
    source = result["retrieved_sources"][0]
    assert source["document_id"] == document.document_id
    assert source["document_title"] == "Approved Lifting Safety Standard"
    assert source["source_reference"] == "TEST-HSE-LIFT-001"
    assert "exclusion zone" in source["relevant_snippet"].lower()


def test_no_source_behavior_never_fabricates_citation(db_session):
    result = retrieve_guidance(db_session, {"hazard": "Suspended load"})
    assert result == no_source_guidance()
    assert result["retrieved_sources"] == []
    assert result["recommended_action"] == "No approved safety reference was retrieved."


def test_verified_historical_corrective_action_memory(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    report = next(row for row in db_session.query(__import__('models').SafetyReport).all() if "suspended" in row.description.lower())
    officer = Actor("Officer", "HSE_OFFICER")
    manager = Actor("Manager", "HSE_MANAGER")
    capa = create_capa(db_session, officer, {"report_id": report.report_id, "title": "Re-establish exclusion zone", "description": "Barricaded the lifting zone and assigned a dedicated banksman.", "priority": "high"})
    assign_capa(db_session, capa, officer, "Supervisor", "SITE_SUPERVISOR")
    transition_capa(db_session, capa, officer, "in_progress")
    transition_capa(db_session, capa, officer, "awaiting_verification", "Controls implemented.")
    verify_closure(db_session, capa, manager, "Verified during lifting restart inspection.")
    db_session.commit()
    matches = [{"report_id": report.report_id, "overall_match_percent": 90.0}]
    actions = historical_corrective_actions(db_session, matches, {"precursor_pattern": report.analysis.precursor_pattern, "critical_control": report.analysis.critical_control})
    assert len(actions) == 1
    assert actions[0]["outcome"] == "Verified closed"
    assert "banksman" in actions[0]["action"].lower()


def test_critical_control_health_uses_transparent_denominator(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    rows = db_session.query(HistoricalAnalysis).all()
    controls = critical_control_health(rows)
    assert controls
    assert sum(row["total_observations"] for row in controls) == len(rows)
    assert all(0 <= row["ineffective_or_degraded_percentage"] <= 100 for row in controls)
    assert all("worker-hours are not available" in row["denominator_note"] for row in controls)
