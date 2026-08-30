from sqlalchemy.orm import Session

from models import CAPA
from services.similarity import categorical_match


def role_recommendation(role: str, analysis: dict, context: dict | None = None) -> dict:
    role = str(role).upper()
    control = str(analysis.get("critical_control") or "the critical control").lower()
    hazard = str(analysis.get("hazard") or "the hazard").lower()
    count = int((context or {}).get("matching_precursor_count", 0))
    recommendations = {
        "WORKER": f"Move away from {hazard}, stop the task, and inform your supervisor.",
        "SITE_SUPERVISOR": f"Stop work, restore and verify {control}, brief the crew, and authorize restart only after the control is effective.",
        "HSE_OFFICER": f"Validate the classification, inspect {control}, and determine whether a corrective or preventive action is required.",
        "HSE_MANAGER": f"Review {count} matching precursor reports, control-health trends, and action effectiveness across affected sites.",
        "AUDITOR": "Review the preserved AI result, latest HSE decision, linked actions, and append-only audit evidence.",
        "ADMIN": "Review the safety facts and coordinate the appropriate HSE workflow without changing the underlying classification.",
    }
    return {
        "role": role,
        "recommendation": recommendations.get(role, recommendations["WORKER"]),
        "classification_unchanged": True,
    }


def historical_corrective_actions(db: Session, similar_reports: list[dict], analysis: dict, limit: int = 5) -> list[dict]:
    match_by_report = {row["report_id"]: row for row in similar_reports}
    if not match_by_report:
        return []
    capas = (
        db.query(CAPA)
        .filter(CAPA.report_id.in_(match_by_report), CAPA.status == "closed", CAPA.verified_at.isnot(None))
        .all()
    )
    rows = []
    for capa in capas:
        match = match_by_report[capa.report_id]
        report_analysis = capa.report.analysis if capa.report else None
        precursor = categorical_match(analysis.get("precursor_pattern"), getattr(report_analysis, "precursor_pattern", ""))
        control = categorical_match(analysis.get("critical_control"), getattr(report_analysis, "critical_control", ""))
        score = 0.7 * (float(match["overall_match_percent"]) / 100) + 0.15 * precursor + 0.15 * control
        rows.append(
            {
                "capa_id": capa.capa_id, "report_id": capa.report_id,
                "related_percent": round(score * 100, 1), "title": capa.title,
                "action": capa.description, "completion_note": capa.completion_note,
                "verification_note": capa.verification_note, "verified_by": capa.verified_by,
                "verified_at": capa.verified_at, "outcome": "Verified closed",
            }
        )
    rows.sort(key=lambda row: (-row["related_percent"], row["capa_id"]))
    return rows[:limit]
