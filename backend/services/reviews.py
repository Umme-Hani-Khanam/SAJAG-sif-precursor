from collections import defaultdict
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import HSEReview, HistoricalAnalysis, SafetyReport
from services.audit import append_audit
from services.roles import Actor


DECISIONS = {"confirmed", "corrected", "rejected", "needs_more_information"}
STATUS_BY_DECISION = {
    "confirmed": "confirmed",
    "corrected": "corrected",
    "rejected": "rejected",
    "needs_more_information": "needs_review",
}
REVIEWED_FIELDS = (
    "risk_level", "sif_score", "hazard", "energy_source", "exposure_type",
    "critical_control", "control_status", "potential_consequence", "likelihood", "precursor",
)


def create_review(db: Session, report: SafetyReport, actor: Actor, payload: dict) -> HSEReview:
    analysis = report.analysis
    if not analysis or analysis.status != "analysed":
        raise HTTPException(status_code=409, detail="Only analysed reports can be reviewed.")
    decision = str(payload.get("decision", "")).lower()
    if decision not in DECISIONS:
        raise HTTPException(status_code=400, detail="Invalid review decision.")
    if decision in {"corrected", "rejected", "needs_more_information"} and not str(payload.get("review_note", "")).strip():
        raise HTTPException(status_code=400, detail="A review note is required for this decision.")
    if decision == "corrected" and not any(payload.get(f"reviewed_{field}") is not None for field in REVIEWED_FIELDS):
        raise HTTPException(status_code=400, detail="Corrected reviews must include at least one reviewed field.")

    review = HSEReview(
        review_id=f"REV-{uuid4().hex[:14].upper()}",
        report_id=report.report_id,
        reviewer_name=actor.name,
        reviewer_role=actor.role,
        review_status=STATUS_BY_DECISION[decision],
        decision=decision,
        ai_risk_level=analysis.risk_level,
        ai_sif_score=analysis.sif_score,
        ai_hazard=analysis.hazard,
        ai_energy_source=analysis.energy_source,
        ai_exposure_type=analysis.exposure_type,
        ai_critical_control=analysis.critical_control,
        ai_control_status=analysis.control_status,
        ai_potential_consequence=analysis.potential_consequence,
        ai_likelihood=analysis.likelihood,
        ai_precursor=analysis.precursor_pattern,
        reviewed_risk_level=payload.get("reviewed_risk_level"),
        reviewed_sif_score=payload.get("reviewed_sif_score"),
        reviewed_hazard=payload.get("reviewed_hazard"),
        reviewed_energy_source=payload.get("reviewed_energy_source"),
        reviewed_exposure_type=payload.get("reviewed_exposure_type"),
        reviewed_critical_control=payload.get("reviewed_critical_control"),
        reviewed_control_status=payload.get("reviewed_control_status"),
        reviewed_potential_consequence=payload.get("reviewed_potential_consequence"),
        reviewed_likelihood=payload.get("reviewed_likelihood"),
        reviewed_precursor=payload.get("reviewed_precursor"),
        review_note=str(payload.get("review_note", "")).strip() or None,
    )
    db.add(review)
    append_audit(
        db, actor, f"HSE_REVIEW_{decision.upper()}", "REPORT", report.report_id,
        old_value=ai_snapshot(analysis), new_value=review_to_dict(review), reason=review.review_note,
    )
    db.flush()
    return review


def ai_snapshot(analysis: HistoricalAnalysis) -> dict:
    return {
        "risk_level": analysis.risk_level, "sif_score": analysis.sif_score,
        "hazard": analysis.hazard, "energy_source": analysis.energy_source,
        "exposure_type": analysis.exposure_type, "critical_control": analysis.critical_control,
        "control_status": analysis.control_status, "potential_consequence": analysis.potential_consequence,
        "likelihood": analysis.likelihood, "precursor": analysis.precursor_pattern,
    }


def review_to_dict(review: HSEReview) -> dict:
    return {column.name: getattr(review, column.name) for column in review.__table__.columns}


def latest_review(report: SafetyReport) -> HSEReview | None:
    return max(report.reviews, key=lambda item: (item.created_at, item.review_id)) if report.reviews else None


def agreement_metrics(db: Session, report_ids: set[str] | None = None) -> dict:
    reviews = db.query(HSEReview).order_by(HSEReview.created_at.asc()).all()
    if report_ids is not None:
        reviews = [review for review in reviews if review.report_id in report_ids]
    latest = {}
    for review in reviews:
        latest[review.report_id] = review
    evaluated = [review for review in latest.values() if review.decision in {"confirmed", "corrected", "rejected"}]
    total = len(evaluated)
    if not total:
        return {
            "reviewed_reports": 0, "hse_agreement_rate": None, "risk_level_agreement": None,
            "precursor_agreement": None, "critical_control_agreement": None,
            "correction_rate": None, "rejected_flag_rate": None,
        }

    def agrees(review, ai_field, reviewed_field):
        if review.decision == "confirmed":
            return True
        if review.decision == "rejected":
            return False
        reviewed = getattr(review, reviewed_field)
        return reviewed is None or _norm(getattr(review, ai_field)) == _norm(reviewed)

    confirmed = sum(review.decision == "confirmed" for review in evaluated)
    return {
        "reviewed_reports": total,
        "hse_agreement_rate": _percent(confirmed, total),
        "risk_level_agreement": _percent(sum(agrees(r, "ai_risk_level", "reviewed_risk_level") for r in evaluated), total),
        "precursor_agreement": _percent(sum(agrees(r, "ai_precursor", "reviewed_precursor") for r in evaluated), total),
        "critical_control_agreement": _percent(sum(agrees(r, "ai_critical_control", "reviewed_critical_control") for r in evaluated), total),
        "correction_rate": _percent(sum(r.decision == "corrected" for r in evaluated), total),
        "rejected_flag_rate": _percent(sum(r.decision == "rejected" for r in evaluated), total),
    }


def _norm(value):
    return " ".join(str(value or "").lower().split())


def _percent(count, total):
    return round(count / total * 100, 1) if total else None
