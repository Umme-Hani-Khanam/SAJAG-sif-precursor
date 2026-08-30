import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from models import AuditEvent
from services.roles import Actor


def append_audit(
    db: Session,
    actor: Actor,
    event_type: str,
    entity_type: str,
    entity_id: str,
    *,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=f"AUD-{uuid4().hex[:16].upper()}",
        actor_name=actor.name,
        actor_role=actor.role,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_value=_json(old_value),
        new_value=_json(new_value),
        reason=reason,
    )
    db.add(event)
    db.flush()
    return event


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def audit_to_dict(event: AuditEvent) -> dict:
    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "actor_name": event.actor_name,
        "actor_role": event.actor_role,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "old_value": json.loads(event.old_value) if event.old_value else None,
        "new_value": json.loads(event.new_value) if event.new_value else None,
        "reason": event.reason,
    }


def query_audit(
    db: Session,
    *,
    event_date: str = "",
    actor: str = "",
    role: str = "",
    event_type: str = "",
    report_id: str = "",
    capa_id: str = "",
) -> list[dict]:
    query = db.query(AuditEvent)
    if actor:
        query = query.filter(AuditEvent.actor_name.ilike(f"%{actor}%"))
    if role:
        query = query.filter(AuditEvent.actor_role == role.upper())
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type.upper())
    if report_id:
        query = query.filter(AuditEvent.entity_type == "REPORT", AuditEvent.entity_id == report_id)
    if capa_id:
        query = query.filter(AuditEvent.entity_type == "CAPA", AuditEvent.entity_id == capa_id)
    if event_date:
        try:
            start = datetime.fromisoformat(event_date).replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(AuditEvent.timestamp >= start, AuditEvent.timestamp < start + timedelta(days=1))
        except ValueError:
            pass
    return [audit_to_dict(event) for event in query.order_by(AuditEvent.timestamp.desc(), AuditEvent.event_id.desc()).all()]
