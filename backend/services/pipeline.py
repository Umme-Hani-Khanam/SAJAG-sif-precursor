import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from models import HistoricalAnalysis, SafetyReport
from services.clustering import assign_to_cluster, cluster_analyses, summarize_clusters
from services.config import ANALYSIS_VERSION, HIGH_RISK_LEVELS
from services.embeddings import build_embedding_text, encode_texts, serialize_embedding
from services.extraction import ANALYSIS_FIELDS, extract_analysis
from services.scoring import risk_level, score_analysis
from services.similarity import preferred_embedding_model, rank_similar_reports
from services.trends import (
    cluster_trend,
    emerging_cluster_patterns,
    parse_report_date,
    staged_unclassified_pattern,
    trend_anchor,
    report_event_date,
)
from services.audit import append_audit
from services.roles import Actor
from services.vector_store import get_vector_store


logger = logging.getLogger("uvicorn.error")


def ensure_analysis_records(db: Session) -> int:
    existing = {row[0] for row in db.query(HistoricalAnalysis.report_id).all()}
    created = 0
    for report_id, in db.query(SafetyReport.report_id).all():
        if report_id not in existing:
            db.add(HistoricalAnalysis(report_id=report_id, status="pending"))
            created += 1
    if created:
        db.flush()
    return created


def mark_analysis_pending(report: SafetyReport) -> None:
    analysis = report.analysis
    if analysis is None:
        analysis = HistoricalAnalysis(report_id=report.report_id)
        report.analysis = analysis
    analysis.status = "pending"
    analysis.error_message = None
    analysis.cluster_id = None
    for field in (
        *ANALYSIS_FIELDS,
        "sif_score",
        "risk_level",
        "embedding",
        "embedding_vector",
        "embedding_model",
        "analysis_timestamp",
        "extraction_model",
        "analysis_version",
    ):
        setattr(analysis, field, None)


def analysis_status(db: Session) -> dict[str, int]:
    ensure_analysis_records(db)
    counts = Counter(str(row.status or "pending") for row in db.query(HistoricalAnalysis).all())
    total = db.query(SafetyReport).count()
    return {
        "total_reports": total,
        "analysed": counts.get("analysed", 0),
        "pending": counts.get("pending", 0),
        "failed": counts.get("failed", 0),
    }


def batch_analyze(
    db: Session,
    *,
    include_failed: bool = True,
    reanalyze_all: bool = False,
    use_gemini: bool = False,
    actor: Actor | None = None,
    progress_callback=None,
    site_scope: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    ensure_analysis_records(db)
    query = db.query(HistoricalAnalysis).join(HistoricalAnalysis.report)
    if site_scope is not None and "*" not in site_scope:
        query = query.filter(SafetyReport.site.in_(site_scope))
    if not reanalyze_all:
        statuses = ["pending", "failed"] if include_failed else ["pending"]
        query = query.filter(HistoricalAnalysis.status.in_(statuses))
    targets = query.order_by(HistoricalAnalysis.report_id.asc()).all()

    prepared = []
    failures = 0
    actor = actor or Actor(name="SAJAG System", role="ADMIN")
    if progress_callback:
        progress_callback(0, 100)
    for index, item in enumerate(targets, start=1):
        try:
            values, extraction_model = extract_analysis(item.report.description, prefer_gemini=use_gemini)
            breakdown = score_analysis(values)
            prepared.append((item, values, extraction_model, breakdown))
        except Exception as exc:
            item.status = "failed"
            item.error_message = str(exc)[:1000]
            failures += 1
        if progress_callback:
            progress_callback(round(index * 80 / len(targets)), 100)

    logger.info(
        "Historical extraction finished targets=%s prepared=%s failures=%s",
        len(targets), len(prepared), failures,
    )
    if progress_callback:
        progress_callback(80, 100)

    if prepared:
        texts = [build_embedding_text(item.report.description, values) for item, values, _, _ in prepared]
        logger.info("Historical embedding generation started count=%s", len(texts))
        vectors, embedding_model = encode_texts(texts)
        logger.info(
            "Historical embedding generation finished count=%s model=%s",
            len(vectors), embedding_model,
        )
        if progress_callback:
            progress_callback(88, 100)
        timestamp = datetime.now(timezone.utc)
        vector_store = get_vector_store(db)
        for (item, values, extraction_model, breakdown), vector in zip(prepared, vectors):
            for field in ANALYSIS_FIELDS:
                setattr(item, field, values[field])
            item.sif_score = float(breakdown["total"])
            item.risk_level = risk_level(item.sif_score)
            vector_store.persist_report_embedding(item, vector, embedding_model)
            item.analysis_timestamp = timestamp
            item.extraction_model = extraction_model
            item.analysis_version = ANALYSIS_VERSION
            item.status = "analysed"
            item.error_message = None
            append_audit(
                db, actor, "REPORT_ANALYSED", "REPORT", item.report_id,
                new_value={"sif_score": item.sif_score, "risk_level": item.risk_level, "analysis_version": ANALYSIS_VERSION},
            )
        logger.info(
            "Historical vector persistence finished count=%s model=%s",
            len(prepared), embedding_model,
        )
    else:
        logger.info("Historical embedding generation skipped; no reports required analysis")
        logger.info("Historical vector persistence finished count=0")

    db.flush()
    if progress_callback:
        progress_callback(95, 100)
    logger.info("Historical clustering started")
    recluster(db)
    logger.info("Historical clustering finished")
    if progress_callback:
        progress_callback(99, 100)
    db.commit()
    logger.info("Historical final commit finished")
    status = analysis_status(db)
    return {
        **status,
        "processed": len(targets),
        "succeeded": len(prepared),
        "failed_this_run": failures,
        "clusters": len(summarize_clusters(_analysed(db))),
    }


def recluster(db: Session) -> dict[str, int]:
    analyses = _analysed(db)
    assignments = cluster_analyses(analyses)
    for item in analyses:
        item.cluster_id = assignments.get(str(item.report_id), -1)
    db.flush()
    return assignments


def _analysed(db: Session) -> list[HistoricalAnalysis]:
    return (
        db.query(HistoricalAnalysis)
        .join(HistoricalAnalysis.report)
        .filter(HistoricalAnalysis.status == "analysed")
        .order_by(HistoricalAnalysis.report_id.asc())
        .all()
    )


def analyze_observation(
    description: str, site: str, activity: str, db: Session,
    site_scope: tuple[str, ...] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    prepared_description = " ".join(str(description or "").split()).strip()
    if not prepared_description:
        raise ValueError("Description must not be empty.")
    values, extraction_model = extract_analysis(prepared_description, prefer_gemini=True)
    histories = _analysed(db)
    if site_scope is not None and "*" not in site_scope:
        allowed = {value.casefold() for value in site_scope}
        histories = [item for item in histories if str(item.report.site).casefold() in allowed]
    model_preference = preferred_embedding_model(histories)
    query_text = build_embedding_text(prepared_description, values)
    vectors, embedding_model = encode_texts([query_text], force_model=model_preference)
    query_vector = vectors[0]
    similarity_histories = histories
    if db.bind and db.bind.dialect.name == "postgresql":
        similarity_histories = [
            item for _, item in get_vector_store(db).search_similar_reports(
                db, query_vector, embedding_model, limit=50,
            ) if item is not None
        ]
    matches = rank_similar_reports(
        values,
        query_vector,
        similarity_histories,
        embedding_model=embedding_model,
    )
    breakdown = score_analysis(values, matches)
    cluster = assign_to_cluster(query_vector, histories, embedding_model)

    as_of = observed_at.date() if isinstance(observed_at, datetime) else trend_anchor(histories)
    cluster_trend_data = None
    emerging_alert = None
    if cluster:
        cluster_items = [item for item in histories if item.cluster_id == cluster["cluster_id"]]
        cluster_trend_data = {
            **cluster_trend(cluster_items, as_of),
            "as_of_date": as_of.isoformat(),
        }
        emerging_alert = next(
            (item for item in emerging_cluster_patterns(histories, as_of=as_of) if item["cluster_id"] == cluster["cluster_id"]),
            None,
        )
        pattern_status = {
            "state": "established_cluster",
            "label": f"Matches established cluster {cluster['cluster_code']}",
            "evidence": [],
        }
    else:
        pattern_status = staged_unclassified_pattern(query_vector, histories, embedding_model, as_of=as_of)

    return {
        "sif_score": float(breakdown["total"]),
        "risk_level": risk_level(breakdown["total"]),
        "score_breakdown": breakdown,
        **values,
        "similar_reports": matches,
        "site": site,
        "activity": activity,
        "current_cluster": cluster,
        "pattern_status": pattern_status,
        "cluster_trend": cluster_trend_data,
        "emerging_risk": emerging_alert,
        "analysis_context": observation_context(histories, site, values, cluster, as_of=as_of),
        "model_metadata": {
            "analysis_version": ANALYSIS_VERSION,
            "extraction_model": extraction_model,
            "embedding_model": embedding_model,
        },
    }


def persist_live_observation(
    db: Session,
    description: str,
    site: str,
    activity: str,
    result: dict[str, Any],
    actor: Actor,
    observed_at: datetime | None = None,
    confidence: dict[str, Any] | None = None,
    input_provenance: dict[str, Any] | None = None,
    photo_findings: dict[str, Any] | None = None,
) -> SafetyReport:
    import json

    observed_at = observed_at or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    submitted_at = datetime.now(timezone.utc)
    report_id = f"OBS-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    report = SafetyReport(
        report_id=report_id,
        date=observed_at.date().isoformat(),
        location_site=site or "Not provided",
        department="Not provided",
        activity=activity or "Not provided",
        report_type="Safety observation",
        shift="Not provided",
        source="Live observation",
        company="Not provided",
        region="Not provided",
        site=site or "Not provided",
        description=description,
        observed_at=observed_at,
        submitted_at=submitted_at,
        submitted_by_user_id=actor.user_id,
        confidence_label=(confidence or {}).get("label"),
        confidence_reasons=json.dumps((confidence or {}).get("reasons", [])),
        review_recommended=bool((confidence or {}).get("hse_review_recommended")),
        input_provenance=json.dumps(input_provenance or {"REPORTED_BY_USER": [description], "OBSERVED_IN_IMAGE": [], "AI_INFERRED": []}),
        photo_findings=json.dumps(photo_findings) if photo_findings else None,
    )
    analysis_values = {field: result.get(field, "") for field in ANALYSIS_FIELDS}
    force_model = (result.get("model_metadata") or {}).get("embedding_model")
    vectors, embedding_model = encode_texts(
        [build_embedding_text(description, analysis_values)], force_model=force_model
    )
    report.analysis = HistoricalAnalysis(
        status="analysed",
        **analysis_values,
        sif_score=float(result["sif_score"]),
        risk_level=result["risk_level"],
        cluster_id=(result.get("current_cluster") or {}).get("cluster_id", -1),
        analysis_timestamp=datetime.now(timezone.utc),
        extraction_model=(result.get("model_metadata") or {}).get("extraction_model"),
        analysis_version=ANALYSIS_VERSION,
    )
    get_vector_store(db).persist_report_embedding(report.analysis, vectors[0], embedding_model)
    db.add(report)
    append_audit(db, actor, "REPORT_SUBMITTED", "REPORT", report_id, new_value={"site": site, "activity": activity, "description": description})
    append_audit(db, Actor(name="SAJAG System", role="ADMIN"), "REPORT_ANALYSED", "REPORT", report_id, new_value={"sif_score": result["sif_score"], "risk_level": result["risk_level"], "precursor": result.get("precursor_pattern")})
    db.flush()
    return report


def observation_context(
    histories: list[HistoricalAnalysis],
    site: str,
    values: dict[str, str],
    cluster: dict | None,
    as_of: date | None = None,
) -> dict:
    normalized_site = site.strip().lower()
    site_items = [
        item
        for item in histories
        if normalized_site and str(item.report.site or item.report.location_site).strip().lower() == normalized_site
    ]
    anchor = as_of or trend_anchor(histories)
    recent_start = anchor - timedelta(days=29)
    recent = [
        item
        for item in histories
        if (parsed := report_event_date(item.report)) and recent_start <= parsed <= anchor
    ]
    precursor = values.get("precursor_pattern", "").strip().lower()
    matching_precursor = sum(str(item.precursor_pattern or "").strip().lower() == precursor for item in histories)
    site_trend = "Not enough site history"
    if site_items:
        current = cluster_trend(site_items, anchor)
        if current["last_30_days"] > current["previous_30_days"]:
            site_trend = "Increasing report frequency"
        elif current["last_30_days"] < current["previous_30_days"]:
            site_trend = "Decreasing report frequency"
        else:
            site_trend = "Stable report frequency"
    return {
        "historical_reports_loaded": len(histories),
        "reports_from_selected_site": len(site_items),
        "recent_reports": len(recent),
        "matching_precursor_count": matching_precursor,
        "current_cluster": cluster,
        "site_trend_indicator": site_trend,
    }


def site_metrics(analyses: list[HistoricalAnalysis]) -> list[dict]:
    grouped: dict[str, list[HistoricalAnalysis]] = defaultdict(list)
    for item in analyses:
        name = str(item.report.site or item.report.location_site or "Unknown")
        grouped[name].append(item)
    rows = []
    for name, items in grouped.items():
        high_critical = sum(str(item.risk_level).lower() in HIGH_RISK_LEVELS for item in items)
        rows.append(
            {
                "site": name,
                "report_volume": len(items),
                "high_critical_count": high_critical,
                "high_critical_percentage": round(high_critical / len(items) * 100, 1),
                "average_sif_score": round(sum(float(item.sif_score or 0) for item in items) / len(items), 1),
            }
        )
    return sorted(rows, key=lambda row: (-row["high_critical_percentage"], -row["average_sif_score"], row["site"]))


def dashboard_metrics(db: Session) -> dict:
    status = analysis_status(db)
    histories = _analysed(db)
    risks = Counter(str(item.risk_level).lower() for item in histories)
    controls = Counter(
        str(item.critical_control)
        for item in histories
        if item.critical_control and str(item.control_status).lower() in {"missing", "failed", "bypassed", "degraded"}
    )
    sites = site_metrics(histories)
    return {
        **status,
        "high_risk_reports": risks.get("high", 0),
        "critical_reports": risks.get("critical", 0),
        "emerging_patterns": len(emerging_cluster_patterns(histories)),
        "unclassified_candidates": sum(item.cluster_id == -1 for item in histories),
        "top_critical_control_failure": controls.most_common(1)[0][0] if controls else "Not available",
        "highest_risk_site": sites[0]["site"] if sites else "Not available",
        "site_metrics": sites,
    }
