from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from models import CAPA, HSEReview, HistoricalAnalysis, SafetyAlert
from services.capa import is_overdue
from services.trends import report_event_date, trend_anchor


INEFFECTIVE = {"degraded", "missing", "failed", "bypassed"}


def critical_control_health(analyses: list[HistoricalAnalysis]) -> list[dict]:
    grouped: dict[str, list[HistoricalAnalysis]] = defaultdict(list)
    for item in analyses:
        if item.status == "analysed" and str(item.critical_control or "").strip():
            grouped[str(item.critical_control).strip()].append(item)
    anchor = trend_anchor(analyses)
    current_start = anchor - timedelta(days=29)
    previous_start = current_start - timedelta(days=30)
    rows = []
    for control, items in grouped.items():
        statuses = Counter(_status_bucket(item.control_status) for item in items)
        ineffective_count = sum(statuses[key] for key in ("degraded", "missing", "failed_bypassed"))
        site_counts = Counter(str(item.report.site or item.report.location_site or "Unknown") for item in items)
        current_ineffective = previous_ineffective = 0
        for item in items:
            parsed = report_event_date(item.report)
            if not parsed or _status_bucket(item.control_status) not in {"degraded", "missing", "failed_bypassed"}:
                continue
            if current_start <= parsed <= anchor:
                current_ineffective += 1
            elif previous_start <= parsed < current_start:
                previous_ineffective += 1
        if current_ineffective > previous_ineffective:
            direction = "worsening"
        elif current_ineffective < previous_ineffective:
            direction = "improving"
        else:
            direction = "stable"
        rows.append(
            {
                "critical_control": control,
                "total_observations": len(items),
                "effective_intact_count": statuses["effective_intact"],
                "degraded_count": statuses["degraded"],
                "missing_count": statuses["missing"],
                "failed_bypassed_count": statuses["failed_bypassed"],
                "unknown_count": statuses["unknown"],
                "ineffective_or_degraded_count": ineffective_count,
                "ineffective_or_degraded_percentage": round(ineffective_count / len(items) * 100, 1),
                "high_critical_reports": sum(str(item.risk_level).lower() in {"high", "critical"} for item in items),
                "sites_affected": sorted(site_counts),
                "top_affected_site": site_counts.most_common(1)[0][0] if site_counts else "",
                "current_30_day_ineffective": current_ineffective,
                "previous_30_day_ineffective": previous_ineffective,
                "trend": direction,
                "as_of_date": anchor.isoformat(),
                "denominator_note": "Percentage uses analysed observations mentioning this control; worker-hours are not available.",
            }
        )
    rows.sort(key=lambda row: ({"worsening": 0, "stable": 1, "improving": 2}[row["trend"]], -row["ineffective_or_degraded_percentage"], row["critical_control"]))
    return rows


def _status_bucket(value: str | None) -> str:
    status = str(value or "unknown").lower()
    if any(term in status for term in ("intact", "effective", "available", "in place", "functional")):
        return "effective_intact"
    if "degraded" in status or "inadequate" in status or "partial" in status or "damaged" in status:
        return "degraded"
    if "missing" in status or "absent" in status or "not used" in status:
        return "missing"
    if "failed" in status or "bypassed" in status or "disabled" in status:
        return "failed_bypassed"
    return "unknown"


def governance_dashboard(db: Session) -> dict:
    latest = {}
    for review in db.query(HSEReview).order_by(HSEReview.created_at.asc()).all():
        latest[review.report_id] = review
    review_counts = Counter(review.review_status for review in latest.values())
    analysed_count = db.query(HistoricalAnalysis).filter(HistoricalAnalysis.status == "analysed").count()
    capas = db.query(CAPA).all()
    alerts = db.query(SafetyAlert).all()
    return {
        "unreviewed_ai_analyses": max(0, analysed_count - len(latest)),
        "confirmed_analyses": review_counts["confirmed"],
        "corrected_analyses": review_counts["corrected"],
        "rejected_analyses": review_counts["rejected"],
        "needs_review_analyses": review_counts["needs_review"],
        "open_capas": sum(capa.status != "closed" for capa in capas),
        "critical_capas": sum(capa.priority == "critical" and capa.status != "closed" for capa in capas),
        "overdue_capas": sum(is_overdue(capa) for capa in capas),
        "awaiting_verification": sum(capa.status == "awaiting_verification" for capa in capas),
        "critical_alerts": sum(alert.severity == "critical" and alert.status in {"open", "acknowledged", "escalated"} for alert in alerts),
    }
