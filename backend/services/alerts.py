import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import HistoricalAnalysis, SafetyAlert, SafetyReport
from services.audit import append_audit
from services.config import CONTROL_ACCELERATION_GROWTH_MULTIPLIER, CONTROL_ACCELERATION_MIN_CURRENT
from services.governance_analytics import critical_control_health
from services.roles import Actor


DECISIONS = {"acknowledge", "dismiss", "escalate"}


def create_analysis_alerts(db: Session, report: SafetyReport, analysis_result: dict, actor: Actor) -> list[SafetyAlert]:
    criteria = []
    if str(analysis_result.get("risk_level", "")).lower() == "critical":
        criteria.append(("critical_observation", "critical", "Critical high-potential safety observation"))
    if analysis_result.get("emerging_risk"):
        criteria.append(("emerging_cluster", "high", "Emerging SIF precursor pattern requires HSE review"))
    control_name = str(analysis_result.get("critical_control") or "").strip().lower()
    if control_name:
        controls = critical_control_health(db.query(HistoricalAnalysis).filter(HistoricalAnalysis.status == "analysed").all())
        control = next((item for item in controls if item["critical_control"].strip().lower() == control_name), None)
        if control and control["current_30_day_ineffective"] >= CONTROL_ACCELERATION_MIN_CURRENT and control["current_30_day_ineffective"] >= max(
            control["previous_30_day_ineffective"] * CONTROL_ACCELERATION_GROWTH_MULTIPLIER,
            control["previous_30_day_ineffective"] + 2,
        ):
            criteria.append(("critical_control_acceleration", "high", f"Critical-control deterioration detected: {control['critical_control']}"))
    created = []
    for alert_type, severity, title in criteria:
        existing = db.query(SafetyAlert).filter_by(report_id=report.report_id, alert_type=alert_type).first()
        if existing:
            continue
        alert = SafetyAlert(
            alert_id=f"ALT-{uuid4().hex[:12].upper()}", report_id=report.report_id,
            cluster_id=(analysis_result.get("current_cluster") or {}).get("cluster_id"),
            alert_type=alert_type, severity=severity, title=title,
            evidence=json.dumps({"sif_score": analysis_result.get("sif_score"), "risk_level": analysis_result.get("risk_level"), "precursor": analysis_result.get("precursor_pattern"), "critical_control": analysis_result.get("critical_control")}, sort_keys=True),
            status="open",
        )
        db.add(alert)
        append_audit(db, actor, "RISK_ESCALATED", "REPORT", report.report_id, new_value={"alert_id": alert.alert_id, "type": alert_type, "severity": severity}, reason="Automated rule created an actionable alert; no CAPA was created automatically.")
        created.append(alert)
    db.flush()
    return created


def decide_alert(db: Session, alert: SafetyAlert, actor: Actor, decision: str, reason: str = "") -> SafetyAlert:
    decision = decision.lower()
    if decision not in DECISIONS:
        raise HTTPException(status_code=400, detail="Invalid alert decision.")
    if decision in {"dismiss", "escalate"} and not str(reason).strip():
        raise HTTPException(status_code=400, detail="A reason is required to dismiss or escalate an alert.")
    old = alert.status
    alert.status = {"acknowledge": "acknowledged", "dismiss": "dismissed", "escalate": "escalated"}[decision]
    alert.decided_at = datetime.now(timezone.utc)
    alert.decided_by = actor.name
    alert.decision_reason = str(reason).strip() or None
    event = {"acknowledge": "ALERT_ACKNOWLEDGED", "dismiss": "ALERT_DISMISSED", "escalate": "RISK_ESCALATED"}[decision]
    append_audit(db, actor, event, "ALERT", alert.alert_id, old_value={"status": old}, new_value={"status": alert.status}, reason=alert.decision_reason)
    db.flush()
    return alert


def alert_to_dict(alert: SafetyAlert) -> dict:
    return {
        "alert_id": alert.alert_id, "report_id": alert.report_id, "cluster_id": alert.cluster_id,
        "alert_type": alert.alert_type, "severity": alert.severity, "title": alert.title,
        "evidence": json.loads(alert.evidence) if alert.evidence else None, "status": alert.status,
        "created_at": alert.created_at, "decided_at": alert.decided_at,
        "decided_by": alert.decided_by, "decision_reason": alert.decision_reason,
        "capa_id": alert.capa.capa_id if alert.capa else None,
    }
