from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from services.clustering import dominant, summarize_clusters
from services.config import (
    EMERGING_CURRENT_WINDOW_DAYS,
    EMERGING_MIN_CURRENT_COUNT,
    EMERGING_MIN_GROWTH_RATIO,
    HIGH_RISK_LEVELS,
    PATTERN_ALERT_MIN_COUNT,
    PATTERN_ALERT_WINDOW_DAYS,
    PATTERN_CANDIDATE_MIN_COUNT,
    UNCLASSIFIED_RELATED_MIN_SIMILARITY,
)
from services.embeddings import cosine_score, deserialize_embedding


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d %b %Y")


def parse_report_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        numeric = float(text)
        if 1 <= numeric <= 100000:
            return date(1899, 12, 30) + timedelta(days=int(numeric))
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def report_event_date(report: Any) -> date | None:
    observed = getattr(report, "observed_at", None)
    return observed.date() if isinstance(observed, datetime) else parse_report_date(getattr(report, "date", None))


def trend_anchor(analyses: list[Any]) -> date:
    dates = [report_event_date(item.report) for item in analyses if getattr(item, "report", None)]
    valid = [value for value in dates if value]
    return max(valid) if valid else date.today()


def _count_between(items: list[Any], start: date, end: date) -> int:
    return sum(
        start <= parsed <= end
        for item in items
        if getattr(item, "report", None)
        for parsed in [report_event_date(item.report)]
        if parsed
    )


def cluster_trend(items: list[Any], as_of: date) -> dict:
    current_start = as_of - timedelta(days=EMERGING_CURRENT_WINDOW_DAYS - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=EMERGING_CURRENT_WINDOW_DAYS - 1)
    current = _count_between(items, current_start, as_of)
    previous = _count_between(items, previous_start, previous_end)
    last_7 = _count_between(items, as_of - timedelta(days=6), as_of)
    last_90 = _count_between(items, as_of - timedelta(days=89), as_of)
    growth_percent = None if previous == 0 else round(((current - previous) / previous) * 100, 1)
    growth_ratio = float("inf") if previous == 0 and current else ((current - previous) / previous if previous else 0)
    emerging = current >= EMERGING_MIN_CURRENT_COUNT and growth_ratio >= EMERGING_MIN_GROWTH_RATIO
    return {
        "last_7_days": last_7,
        "last_30_days": current,
        "previous_30_days": previous,
        "last_90_days": last_90,
        "growth_percent": growth_percent,
        "emerging": emerging,
    }


def emerging_cluster_patterns(analyses: list[Any], as_of: date | None = None) -> list[dict]:
    as_of = as_of or trend_anchor(analyses)
    summaries = {item["cluster_id"]: item for item in summarize_clusters(analyses)}
    grouped: dict[int, list[Any]] = defaultdict(list)
    for item in analyses:
        if getattr(item, "cluster_id", None) is not None and item.cluster_id >= 0:
            grouped[item.cluster_id].append(item)
    results = []
    for cluster_id, items in sorted(grouped.items()):
        stats = cluster_trend(items, as_of)
        if not stats["emerging"]:
            continue
        summary = summaries[cluster_id]
        results.append(
            {
                **summary,
                **stats,
                "as_of_date": as_of.isoformat(),
                "alert_title": "Emerging SIF precursor pattern detected",
                "sites_affected_count": len(summary["sites_affected"]),
                "potential_consequence": dominant(items, "potential_consequence"),
                "evidence_report_ids": [str(item.report_id) for item in sorted(items, key=lambda row: str(row.report_id))],
                "rule": {
                    "minimum_current_count": EMERGING_MIN_CURRENT_COUNT,
                    "minimum_growth_percent": round(EMERGING_MIN_GROWTH_RATIO * 100),
                    "window_days": EMERGING_CURRENT_WINDOW_DAYS,
                },
            }
        )
    results.sort(key=lambda item: (-item["last_30_days"], item["cluster_id"]))
    return results


def staged_unclassified_pattern(
    query_vector,
    analyses: list[Any],
    embedding_model: str,
    as_of: date | None = None,
) -> dict:
    as_of = as_of or trend_anchor(analyses)
    related = []
    for item in analyses:
        vector = deserialize_embedding(getattr(item, "embedding", None))
        if (
            getattr(item, "status", "") == "analysed"
            and getattr(item, "cluster_id", None) == -1
            and item.embedding_model == embedding_model
            and vector is not None
            and vector.shape == query_vector.shape
        ):
            similarity = cosine_score(query_vector, vector)
            if similarity >= UNCLASSIFIED_RELATED_MIN_SIMILARITY:
                related.append((item, similarity, report_event_date(item.report)))

    total_with_current = len(related) + 1
    window_start = as_of - timedelta(days=PATTERN_ALERT_WINDOW_DAYS - 1)
    recent = [entry for entry in related if entry[2] and window_start <= entry[2] <= as_of]
    recent_with_current = len(recent) + 1
    if total_with_current < PATTERN_CANDIDATE_MIN_COUNT:
        state = "monitor"
        label = "Unrecognized precursor candidate"
    elif recent_with_current >= PATTERN_ALERT_MIN_COUNT:
        state = "new_pattern_alert"
        label = "New precursor pattern alert"
    else:
        state = "candidate_pattern"
        label = "Candidate precursor pattern"
    evidence = sorted(related, key=lambda row: (-row[1], str(row[0].report_id)))
    return {
        "state": state,
        "label": label,
        "related_unclassified_count": len(related),
        "recent_related_count": len(recent),
        "window_days": PATTERN_ALERT_WINDOW_DAYS,
        "evidence": [
            {
                "report_id": str(item.report_id),
                "date": str(item.report.date),
                "description": str(item.report.description),
                "semantic_similarity_percent": round(score * 100, 1),
            }
            for item, score, _ in evidence[:5]
        ],
    }


def analytics_series(analyses: list[Any]) -> dict:
    monthly: dict[str, dict] = defaultdict(
        lambda: {"reports": 0, "high_critical": 0, "precursors": Counter(), "controls": Counter()}
    )
    for item in analyses:
        parsed = report_event_date(item.report) if getattr(item, "report", None) else None
        if getattr(item, "status", "") != "analysed" or not parsed:
            continue
        key = parsed.strftime("%Y-%m")
        monthly[key]["reports"] += 1
        monthly[key]["high_critical"] += str(item.risk_level).lower() in HIGH_RISK_LEVELS
        if item.precursor_pattern:
            monthly[key]["precursors"][str(item.precursor_pattern)] += 1
        if item.critical_control and str(item.control_status).lower() in {"missing", "failed", "bypassed", "degraded"}:
            monthly[key]["controls"][str(item.critical_control)] += 1

    points = []
    for period in sorted(monthly):
        values = monthly[period]
        points.append(
            {
                "period": period,
                "reports": values["reports"],
                "high_critical": values["high_critical"],
                "top_precursor": values["precursors"].most_common(1)[0][0] if values["precursors"] else "",
                "top_precursor_count": values["precursors"].most_common(1)[0][1] if values["precursors"] else 0,
                "critical_control_failures": sum(values["controls"].values()),
            }
        )
    precursor_frequency = Counter(str(item.precursor_pattern) for item in analyses if getattr(item, "precursor_pattern", None))
    control_frequency = Counter(
        str(item.critical_control)
        for item in analyses
        if getattr(item, "critical_control", None) and str(item.control_status).lower() in {"missing", "failed", "bypassed", "degraded"}
    )
    return {
        "series": points,
        "precursor_frequency": [{"name": name, "count": count} for name, count in precursor_frequency.most_common()],
        "critical_control_failures": [{"name": name, "count": count} for name, count in control_frequency.most_common()],
    }
