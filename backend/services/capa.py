from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import CAPA, CAPAEvidence
from services.audit import append_audit
from services.roles import Actor


ACTION_TYPES = {"corrective", "preventive", "investigation"}
PRIORITIES = {"low", "medium", "high", "critical"}
STATES = {"open", "assigned", "in_progress", "awaiting_verification", "closed", "reopened"}
ALLOWED_TRANSITIONS = {
    "open": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"awaiting_verification"},
    "awaiting_verification": set(),
    "closed": {"reopened"},
    "reopened": {"assigned", "in_progress"},
}


def create_capa(db: Session, actor: Actor, payload: dict) -> CAPA:
    action_type = str(payload.get("action_type", "corrective")).lower()
    priority = str(payload.get("priority", "medium")).lower()
    if action_type not in ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid CAPA action type.")
    if priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid CAPA priority.")
    due_date = _parse_datetime(payload.get("due_date"))
    capa = CAPA(
        capa_id=f"CAPA-{uuid4().hex[:12].upper()}",
        report_id=payload.get("report_id") or None,
        cluster_id=payload.get("cluster_id"),
        alert_id=payload.get("alert_id") or None,
        title=str(payload.get("title", "")).strip(),
        description=str(payload.get("description", "")).strip(),
        action_type=action_type,
        priority=priority,
        owner_name=payload.get("owner_name") or None,
        owner_role=(str(payload.get("owner_role", "")).upper() or None),
        created_by=actor.name,
        created_by_role=actor.role,
        due_date=due_date,
        status="open",
    )
    if not capa.title or not capa.description:
        raise HTTPException(status_code=400, detail="CAPA title and description are required.")
    db.add(capa)
    append_audit(db, actor, "CAPA_CREATED", "CAPA", capa.capa_id, new_value=capa_to_dict(capa))
    db.flush()
    if capa.owner_name:
        assign_capa(db, capa, actor, capa.owner_name, capa.owner_role or "SITE_SUPERVISOR")
    return capa


def assign_capa(db: Session, capa: CAPA, actor: Actor, owner_name: str, owner_role: str) -> CAPA:
    if capa.status not in {"open", "reopened", "assigned"}:
        raise HTTPException(status_code=409, detail=f"Cannot assign a CAPA in {capa.status} status.")
    old = {"status": capa.status, "owner_name": capa.owner_name, "owner_role": capa.owner_role}
    capa.owner_name = str(owner_name).strip()
    capa.owner_role = str(owner_role).strip().upper()
    capa.status = "assigned"
    append_audit(db, actor, "CAPA_ASSIGNED", "CAPA", capa.capa_id, old_value=old, new_value={"status": capa.status, "owner_name": capa.owner_name, "owner_role": capa.owner_role})
    db.flush()
    return capa


def transition_capa(db: Session, capa: CAPA, actor: Actor, target: str, note: str = "") -> CAPA:
    target = target.lower()
    if target not in STATES:
        raise HTTPException(status_code=400, detail="Unknown CAPA status.")
    if target == "closed":
        raise HTTPException(status_code=409, detail="CAPA closure requires the verification endpoint.")
    if target not in ALLOWED_TRANSITIONS.get(capa.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid CAPA transition: {capa.status} -> {target}.")
    old_status = capa.status
    capa.status = target
    if target == "awaiting_verification":
        capa.completion_note = str(note).strip() or capa.completion_note
        capa.completed_at = datetime.now(timezone.utc)
    event_type = "CAPA_REOPENED" if target == "reopened" else "CAPA_STATUS_CHANGED"
    append_audit(db, actor, event_type, "CAPA", capa.capa_id, old_value={"status": old_status}, new_value={"status": target}, reason=note or None)
    db.flush()
    return capa


def verify_closure(db: Session, capa: CAPA, actor: Actor, note: str) -> CAPA:
    if capa.status != "awaiting_verification":
        raise HTTPException(status_code=409, detail="Only CAPAs awaiting verification can be closed.")
    if not str(note).strip():
        raise HTTPException(status_code=400, detail="A verification note is required.")
    capa.status = "closed"
    capa.verification_note = str(note).strip()
    capa.verified_at = datetime.now(timezone.utc)
    capa.verified_by = actor.name
    append_audit(db, actor, "CAPA_CLOSED", "CAPA", capa.capa_id, old_value={"status": "awaiting_verification"}, new_value={"status": "closed", "verified_by": actor.name}, reason=note)
    db.flush()
    return capa


def add_evidence(db: Session, capa: CAPA, actor: Actor, payload: dict) -> CAPAEvidence:
    note = str(payload.get("note", "")).strip()
    if not note:
        raise HTTPException(status_code=400, detail="Evidence note is required.")
    evidence = CAPAEvidence(
        evidence_id=f"EVD-{uuid4().hex[:14].upper()}",
        capa_id=capa.capa_id,
        evidence_type=str(payload.get("evidence_type", "note")).strip().lower(),
        reference=str(payload.get("reference", "")).strip() or None,
        note=note,
        added_by=actor.name,
        added_by_role=actor.role,
    )
    db.add(evidence)
    append_audit(db, actor, "CAPA_EVIDENCE_ADDED", "CAPA", capa.capa_id, new_value={"evidence_id": evidence.evidence_id, "type": evidence.evidence_type, "reference": evidence.reference}, reason=note)
    db.flush()
    return evidence


def is_overdue(capa: CAPA, now: datetime | None = None) -> bool:
    if not capa.due_date or capa.status == "closed":
        return False
    now = now or datetime.now(timezone.utc)
    due = capa.due_date
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due < now


def capa_to_dict(capa: CAPA) -> dict:
    return {
        "capa_id": capa.capa_id, "report_id": capa.report_id, "cluster_id": capa.cluster_id,
        "alert_id": capa.alert_id, "title": capa.title, "description": capa.description,
        "action_type": capa.action_type, "priority": capa.priority,
        "owner_name": capa.owner_name, "owner_role": capa.owner_role,
        "created_by": capa.created_by, "created_by_role": capa.created_by_role,
        "created_at": capa.created_at, "due_date": capa.due_date, "status": capa.status,
        "effective_status": "overdue" if is_overdue(capa) else capa.status,
        "is_overdue": is_overdue(capa), "completion_note": capa.completion_note,
        "verification_note": capa.verification_note, "completed_at": capa.completed_at,
        "verified_at": capa.verified_at, "verified_by": capa.verified_by,
        "evidence": [evidence_to_dict(item) for item in sorted(capa.evidence, key=lambda row: row.created_at)],
    }


def evidence_to_dict(item: CAPAEvidence) -> dict:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="due_date must be an ISO date or datetime.") from exc
