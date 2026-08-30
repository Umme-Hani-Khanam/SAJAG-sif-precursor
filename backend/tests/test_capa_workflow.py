from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from services.capa import add_evidence, assign_capa, create_capa, is_overdue, transition_capa, verify_closure
from services.roles import Actor


def test_capa_required_flow_and_verified_closure(db_session):
    officer = Actor("HSE Officer", "HSE_OFFICER")
    supervisor = Actor("Site Supervisor", "SITE_SUPERVISOR")
    manager = Actor("HSE Manager", "HSE_MANAGER")
    capa = create_capa(db_session, officer, {"title": "Restore lifting exclusion zone", "description": "Install rigid barricades and nominate a banksman.", "action_type": "corrective", "priority": "critical", "due_date": datetime.now(timezone.utc) + timedelta(days=2)})
    assign_capa(db_session, capa, officer, "Site Supervisor", "SITE_SUPERVISOR")
    transition_capa(db_session, capa, supervisor, "in_progress", "Barricades procured.")
    evidence = add_evidence(db_session, capa, supervisor, {"evidence_type": "inspection_note", "reference": "SAFE-42", "note": "Barricades installed and toolbox talk recorded."})
    transition_capa(db_session, capa, supervisor, "awaiting_verification", "Implementation completed.")
    verify_closure(db_session, capa, manager, "Field verification confirmed the exclusion zone and banksman control.")
    db_session.commit()

    assert capa.status == "closed"
    assert capa.verified_by == manager.name and capa.verified_at is not None
    assert evidence in capa.evidence
    event_types = [event.event_type for event in db_session.query(__import__('models').AuditEvent).filter_by(entity_id=capa.capa_id).all()]
    assert {"CAPA_CREATED", "CAPA_ASSIGNED", "CAPA_STATUS_CHANGED", "CAPA_EVIDENCE_ADDED", "CAPA_CLOSED"}.issubset(event_types)


def test_invalid_capa_transitions_are_blocked(db_session):
    actor = Actor("Officer", "HSE_OFFICER")
    capa = create_capa(db_session, actor, {"title": "Investigate", "description": "Complete investigation.", "action_type": "investigation", "priority": "high"})
    with pytest.raises(HTTPException, match="Invalid CAPA transition"):
        transition_capa(db_session, capa, actor, "in_progress")
    assign_capa(db_session, capa, actor, "Supervisor", "SITE_SUPERVISOR")
    transition_capa(db_session, capa, actor, "in_progress")
    with pytest.raises(HTTPException, match="verification endpoint"):
        transition_capa(db_session, capa, actor, "closed")
    with pytest.raises(HTTPException, match="awaiting verification"):
        verify_closure(db_session, capa, actor, "Premature closure")


def test_overdue_is_derived_without_destroying_workflow_status(db_session):
    actor = Actor("Officer", "HSE_OFFICER")
    capa = create_capa(db_session, actor, {"title": "Past due action", "description": "Outstanding control action.", "due_date": datetime.now(timezone.utc) - timedelta(days=1)})
    assert capa.status == "open"
    assert is_overdue(capa)
