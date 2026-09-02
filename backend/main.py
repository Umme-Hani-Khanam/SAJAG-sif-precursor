import csv
import json
import os
import re
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pypdf import PdfReader
from sqlalchemy import inspect
from sqlalchemy.orm import Session, joinedload

from database import Base, SessionLocal, engine, get_db
from intelligence import analyze_description
from models import Attachment, BackgroundJob, CAPA, HSEReview, HistoricalAnalysis, Notification, PhotoAnalysis, SafetyAlert, SafetyDocument, SafetyReport, User, ValidationCase, ValidationDataset, ValidationRun
from schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AlertDecisionRequest,
    BatchAnalyzeRequest,
    CAPAAssign,
    CAPACreate,
    CAPAEvidenceCreate,
    CAPAStatusChange,
    HealthResponse,
    LoginRequest,
    NoteRequest,
    ReviewCreate,
    SafetyReportResponse,
    UploadResponse,
    UserCreate,
)
from services.auth import authenticate, create_session, create_user, revoke_session, safe_user
from services.alerts import alert_to_dict, create_analysis_alerts, decide_alert
from services.audit import append_audit, query_audit
from services.capa import add_evidence, assign_capa, capa_to_dict, create_capa, is_overdue, transition_capa, verify_closure
from services.clustering import summarize_clusters
from services.governance_analytics import critical_control_health, governance_dashboard
from services.knowledge import document_to_dict, index_document_content, ingest_document, retrieve_guidance, transition_document
from services.jobs import create_job, job_to_dict, recover_interrupted_jobs, register_handler, submit_persisted_job
from services.notifications import create_notification, mark_all_read, mark_read, notification_query, notification_to_dict, unread_notification_query
from services.ocr import extract_pdf_with_fallback
from services.photo import analyze_photo, combined_description
from services.pipeline import (
    analysis_status,
    batch_analyze,
    dashboard_metrics,
    ensure_analysis_records,
    mark_analysis_pending,
    persist_live_observation,
    site_metrics,
)
from services.recommendations import historical_corrective_actions, role_recommendation
from services.reviews import agreement_metrics, create_review, latest_review, review_to_dict
from services.confidence import assess_confidence
from services.roles import Actor, get_actor, has_permission, permission_matrix, require, require_site, scoped_sites
from services.storage import LocalFileStorage, attachment_to_dict, save_attachment, validate_file
from services.trends import analytics_series, cluster_trend, emerging_cluster_patterns, parse_report_date, report_event_date, trend_anchor
from services.validation import GROUND_TRUTH_COLUMNS, run_to_dict, run_validation


APP_NAME = os.getenv("APP_NAME", "SAJAG SIF Precursor Intelligence API")
DEMO_MODE_CONFIGURED = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
CORS_ORIGINS = [item.strip() for item in os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
).split(",") if item.strip()]
if not DEMO_MODE_CONFIGURED and "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS may not contain '*' when DEMO_MODE=false.")
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "safety_reports.xlsx"

REQUIRED_COLUMNS = [
    "Report ID", "Date", "Location/Site", "Department", "Activity", "Report Type",
    "Shift", "Source", "Company", "Region", "Site", "Description",
]
COLUMN_MAPPING = {
    "Report ID": "report_id", "Date": "date", "Location/Site": "location_site",
    "Department": "department", "Activity": "activity", "Report Type": "report_type",
    "Shift": "shift", "Source": "source", "Company": "company", "Region": "region",
    "Site": "site", "Description": "description",
}
EXPORT_COLUMNS = [
    ("Report ID", "report_id"), ("Date", "date"), ("Site", "site"),
    ("Department", "department"), ("Activity", "activity"), ("Description", "description"),
    ("Hazard", "hazard"), ("Energy Source", "energy_source"), ("Exposure Type", "exposure_type"),
    ("Unsafe Act", "unsafe_act"), ("Unsafe Condition", "unsafe_condition"),
    ("Critical Control", "critical_control"), ("Control Status", "control_status"),
    ("Potential Consequence", "potential_consequence"), ("Likelihood", "likelihood"),
    ("Precursor", "precursor_pattern"), ("SIF Score", "sif_score"),
    ("Risk Level", "risk_level"), ("Cluster ID", "cluster_id"), ("Analysis Status", "status"),
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    on_startup()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", *(["X-Actor-Name", "X-Actor-Role"] if DEMO_MODE_CONFIGURED else [])],
)


def on_startup() -> None:
    demo_mode = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
    auto_create = os.getenv("AUTO_CREATE_SCHEMA", "true" if demo_mode else "false").strip().lower() in {"1", "true", "yes", "on"}
    if auto_create:
        Base.metadata.create_all(bind=engine)
    elif not inspect(engine).has_table("users"):
        raise RuntimeError("Database schema is not migrated. Run: alembic upgrade head")
    seed_default_dataset()
    db = SessionLocal()
    try:
        recover_interrupted_jobs(db)
        ensure_analysis_records(db)
        db.commit()
    finally:
        db.close()


def _historical_job(db: Session, payload: dict, progress) -> dict:
    actor = Actor(
        payload.get("actor_name", "SAJAG System"), payload.get("actor_role", "ADMIN"),
        payload.get("actor_user_id"), tuple(payload.get("site_scope", ["*"])), True,
    )
    return batch_analyze(
        db, include_failed=bool(payload.get("include_failed", True)),
        reanalyze_all=bool(payload.get("reanalyze_all", False)),
        use_gemini=bool(payload.get("use_gemini", False)), actor=actor,
        progress_callback=progress,
        site_scope=scoped_sites(actor),
    )


register_handler("HISTORICAL_ANALYSIS", _historical_job)


def _document_index_job(db: Session, payload: dict, progress) -> dict:
    document = db.get(SafetyDocument, payload["document_id"])
    attachment = db.get(Attachment, payload["attachment_id"])
    if document is None or attachment is None:
        raise RuntimeError("Document indexing source no longer exists.")
    actor = Actor(
        payload.get("actor_name", "SAJAG System"), payload.get("actor_role", "ADMIN"),
        payload.get("actor_user_id"), tuple(payload.get("site_scope", ["*"])), True,
    )
    try:
        content = LocalFileStorage().path_for(attachment.storage_key).read_bytes()
        index_document_content(db, document, actor, content, progress)
        db.commit()
        return {"document_id": document.document_id, "chunks": document.chunk_count, "status": document.status}
    except Exception:
        db.rollback()
        document = db.get(SafetyDocument, payload["document_id"])
        if document:
            document.indexing_status = "failed"
            db.commit()
        raise


register_handler("DOCUMENT_INDEXING", _document_index_job)


def _ocr_job(db: Session, payload: dict, progress) -> dict:
    attachment = db.get(Attachment, payload["attachment_id"])
    if attachment is None:
        raise RuntimeError("OCR source attachment no longer exists.")
    progress(0, 1)
    content = LocalFileStorage().path_for(attachment.storage_key).read_bytes()
    extraction = extract_pdf_with_fallback(content)
    actor = Actor(
        payload.get("actor_name", "SAJAG System"), payload.get("actor_role", "ADMIN"),
        payload.get("actor_user_id"), tuple(payload.get("site_scope", ["*"])), True,
    )
    observed = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00")) if payload.get("observed_at") else None
    result = analyze_report(
        AnalyzeRequest(
            description=extraction["text"], site=payload.get("site", ""),
            activity=payload.get("activity", ""), observed_at=observed,
        ), db=db, actor=actor,
    )
    result["document_extraction"] = {key: value for key, value in extraction.items() if key != "text"}
    attachment.entity_type, attachment.entity_id = "REPORT", result["report_id"]
    db.commit()
    progress(1, 1)
    return result


def _photo_job(db: Session, payload: dict, progress) -> dict:
    attachment = db.get(Attachment, payload["attachment_id"])
    if attachment is None:
        raise RuntimeError("Photo source attachment no longer exists.")
    progress(0, 1)
    content = LocalFileStorage().path_for(attachment.storage_key).read_bytes()
    findings = analyze_photo(content, attachment.media_type, payload.get("description", ""))
    combined, provenance = combined_description(payload.get("description", ""), findings)
    actor = Actor(
        payload.get("actor_name", "SAJAG System"), payload.get("actor_role", "ADMIN"),
        payload.get("actor_user_id"), tuple(payload.get("site_scope", ["*"])), True,
    )
    observed = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00")) if payload.get("observed_at") else None
    result = analyze_report(
        AnalyzeRequest(
            description=combined, site=payload.get("site", ""),
            activity=payload.get("activity", ""), observed_at=observed,
        ), db=db, actor=actor,
    )
    report = db.get(SafetyReport, result["report_id"])
    confidence = assess_confidence(
        description=payload.get("description", ""), site=payload.get("site", ""),
        activity=payload.get("activity", ""), analysis=result,
        text_source="image", input_quality=findings["confidence"],
    )
    report.input_provenance, report.photo_findings = json.dumps(provenance), json.dumps(findings)
    report.confidence_label, report.confidence_reasons = confidence["label"], json.dumps(confidence["reasons"])
    report.review_recommended = confidence["hse_review_recommended"]
    attachment.entity_type, attachment.entity_id = "REPORT", report.report_id
    db.add(PhotoAnalysis(
        photo_analysis_id=f"IMG-{uuid4().hex[:16].upper()}", report_id=report.report_id,
        attachment_id=attachment.attachment_id, visible_hazards=json.dumps(findings["visible_hazards"]),
        visible_controls=json.dumps(findings["visible_controls"]),
        possible_missing_controls=json.dumps(findings["possible_missing_controls"]),
        possible_exposures=json.dumps(findings["possible_exposures"]), image_summary=findings["image_summary"],
        confidence=findings["confidence"], provider="gemini",
    ))
    if confidence["hse_review_recommended"]:
        create_notification(
            db, notification_type="LOW_CONFIDENCE_HIGH_RISK", title="HSE review recommended",
            message=f"High-consequence photo report {report.report_id} has low evidence confidence.",
            entity_type="REPORT", entity_id=report.report_id,
            dedupe_key=f"low-confidence:{report.report_id}", recipient_role="HSE_OFFICER",
            recipient_site=report.site,
        )
    result.update({"photo_findings": findings, "input_provenance": provenance, "confidence": confidence, "hse_review_recommended": confidence["hse_review_recommended"], "attachment": attachment_to_dict(attachment)})
    db.commit()
    progress(1, 1)
    return result


register_handler("OCR_PROCESSING", _ocr_job)
register_handler("PHOTO_ANALYSIS", _photo_job)


def seed_default_dataset() -> None:
    if not DEFAULT_DATASET_PATH.exists():
        return
    db = SessionLocal()
    try:
        if db.query(SafetyReport).count() > 0:
            return
        dataframe = pd.read_excel(
            DEFAULT_DATASET_PATH, engine="openpyxl", dtype=str, keep_default_na=False, na_filter=False
        )
        validate_required_columns(dataframe)
        for row in dataframe[REQUIRED_COLUMNS].to_dict(orient="records"):
            payload = {COLUMN_MAPPING[column]: value for column, value in row.items()}
            report = SafetyReport(**payload)
            report.analysis = HistoricalAnalysis(status="pending")
            db.add(report)
        db.commit()
    finally:
        db.close()


def read_uploaded_dataframe(upload_file: UploadFile) -> pd.DataFrame:
    extension = os.path.splitext(upload_file.filename or "")[1].lower()
    try:
        file_bytes = upload_file.file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if extension == ".csv":
            return pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False, na_filter=False)
        if extension == ".xlsx":
            return pd.read_excel(
                BytesIO(file_bytes), engine="openpyxl", dtype=str, keep_default_na=False, na_filter=False
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Uploaded dataset could not be parsed as the declared file type.") from exc
    raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .csv or .xlsx file.")


def validate_required_columns(dataframe: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"message": "Uploaded file is missing required columns.", "missing_columns": missing, "required_columns": REQUIRED_COLUMNS},
        )


def extract_text_from_pdf(upload_file: UploadFile) -> str:
    if os.path.splitext(upload_file.filename or "")[1].lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .pdf file.")
    try:
        file_bytes = upload_file.file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        reader = PdfReader(BytesIO(file_bytes))
        cleaned = re.sub(r"\s+", " ", "\n".join(page.extract_text() or "" for page in reader.pages)).strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF content could not be parsed.") from exc
    if not cleaned:
        raise HTTPException(status_code=400, detail="PDF text could not be extracted. Scanned/image PDFs are not supported.")
    return cleaned


def filtered_analyses(
    db: Session,
    *,
    date_from: str = "",
    date_to: str = "",
    site: str = "",
    department: str = "",
    activity: str = "",
    risk_level: str = "",
    precursor: str = "",
    cluster_id: int | None = None,
    actor: Actor | None = None,
) -> list[HistoricalAnalysis]:
    items = (
        db.query(HistoricalAnalysis)
        .options(joinedload(HistoricalAnalysis.report))
        .join(HistoricalAnalysis.report)
        .order_by(SafetyReport.date.asc(), SafetyReport.report_id.asc())
        .all()
    )
    start, end = parse_report_date(date_from), parse_report_date(date_to)

    def matches(item: HistoricalAnalysis) -> bool:
        report = item.report
        parsed = report_event_date(report)
        allowed_sites = scoped_sites(actor) if actor else None
        actor_denied = bool(allowed_sites is not None and str(report.site).casefold() not in {value.casefold() for value in allowed_sites})
        worker_denied = bool(actor and actor.role == "WORKER" and actor.user_id and report.submitted_by_user_id != actor.user_id)
        return not any(
            [
                actor_denied,
                worker_denied,
                start and (not parsed or parsed < start),
                end and (not parsed or parsed > end),
                site and site.lower() not in str(report.site or report.location_site).lower(),
                department and department.lower() not in str(report.department).lower(),
                activity and activity.lower() not in str(report.activity).lower(),
                risk_level and risk_level.lower() != str(item.risk_level or "").lower(),
                precursor and precursor.lower() not in str(item.precursor_pattern or "").lower(),
                cluster_id is not None and cluster_id != item.cluster_id,
            ]
        )

    return [item for item in items if matches(item)]


def _dashboard_from_items(items: list[HistoricalAnalysis]) -> dict:
    risks = Counter(str(item.risk_level or "").lower() for item in items)
    controls = Counter(
        str(item.critical_control) for item in items
        if item.critical_control and str(item.control_status).lower() in {"missing", "failed", "bypassed", "degraded"}
    )
    sites = site_metrics(items)
    return {
        "total_reports": len(items), "analysed": sum(item.status == "analysed" for item in items),
        "pending": sum(item.status == "pending" for item in items),
        "failed": sum(item.status == "failed" for item in items),
        "high_risk_reports": risks.get("high", 0), "critical_reports": risks.get("critical", 0),
        "emerging_patterns": len(emerging_cluster_patterns(items)),
        "unclassified_candidates": sum(item.cluster_id == -1 for item in items),
        "top_critical_control_failure": controls.most_common(1)[0][0] if controls else "Not available",
        "highest_risk_site": sites[0]["site"] if sites else "Not available", "site_metrics": sites,
    }


def _scoped_governance_dashboard(db: Session, items: list[HistoricalAnalysis]) -> dict:
    report_ids = {item.report_id for item in items}
    latest = {}
    for review in db.query(HSEReview).filter(HSEReview.report_id.in_(report_ids or {"__none__"})).order_by(HSEReview.created_at.asc()).all():
        latest[review.report_id] = review
    review_counts = Counter(review.review_status for review in latest.values())
    capas = db.query(CAPA).filter(CAPA.report_id.in_(report_ids or {"__none__"})).all()
    alerts = db.query(SafetyAlert).filter(SafetyAlert.report_id.in_(report_ids or {"__none__"})).all()
    analysed = sum(item.status == "analysed" for item in items)
    return {
        "unreviewed_ai_analyses": max(0, analysed - len(latest)),
        "confirmed_analyses": review_counts["confirmed"], "corrected_analyses": review_counts["corrected"],
        "rejected_analyses": review_counts["rejected"], "needs_review_analyses": review_counts["needs_review"],
        "open_capas": sum(capa.status != "closed" for capa in capas),
        "critical_capas": sum(capa.priority == "critical" and capa.status != "closed" for capa in capas),
        "overdue_capas": sum(is_overdue(capa) for capa in capas),
        "awaiting_verification": sum(capa.status == "awaiting_verification" for capa in capas),
        "critical_alerts": sum(alert.severity == "critical" and alert.status in {"open", "acknowledged", "escalated"} for alert in alerts),
    }


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok", message="SAJAG backend is running.",
        demo_mode=os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes", "on"},
    )


@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate(db, request.identifier, request.password)
    token, session = create_session(db, user)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": session.expires_at, "user": safe_user(user)}


@app.get("/auth/me")
def auth_me(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)) -> dict:
    if actor.user_id:
        from models import User
        return safe_user(db.get(User, actor.user_id))
    return {"user_id": None, "name": actor.name, "role": actor.role, "site_scope": list(actor.site_scope), "demo": True}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication session is required.")
    revoke_session(db, authorization.split(" ", 1)[1])
    db.commit()
    return {"message": "Signed out."}


@app.post("/auth/users")
def add_user(request: UserCreate, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)) -> dict:
    require(actor, "ADMIN_USERS")
    try:
        user = create_user(db, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return safe_user(user)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_report(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AnalyzeResponse:
    require(actor, "SUBMIT_REPORT")
    if not request.site:
        sites = scoped_sites(actor)
        if sites and len(sites) == 1:
            request = request.model_copy(update={"site": sites[0]})
        elif actor.authenticated and sites is not None:
            raise HTTPException(status_code=400, detail="A site from the account's authorized scope is required.")
    if request.site:
        require_site(actor, request.site)
    result = analyze_description(
        request.description, request.site, request.activity, db=db,
        site_scope=scoped_sites(actor), observed_at=request.observed_at,
    )
    result["grounded_guidance"] = retrieve_guidance(db, result, observed_at=request.observed_at)
    result["historical_actions"] = historical_corrective_actions(db, result["similar_reports"], result)
    result["role_recommendation"] = role_recommendation(actor.role, result, result.get("analysis_context"))
    confidence = assess_confidence(
        description=request.description, site=request.site, activity=request.activity, analysis=result,
    )
    report = persist_live_observation(
        db, request.description, request.site, request.activity, result, actor,
        observed_at=request.observed_at, confidence=confidence,
    )
    alerts = create_analysis_alerts(db, report, result, Actor(name="SAJAG System", role="ADMIN"))
    result["report_id"] = report.report_id
    result["alerts"] = [alert_to_dict(item) for item in alerts]
    result["observed_at"] = report.observed_at
    result["submitted_at"] = report.submitted_at
    result["confidence"] = confidence
    result["hse_review_recommended"] = confidence["hse_review_recommended"]
    result["input_provenance"] = json.loads(report.input_provenance)
    if str(result["risk_level"]).lower() in {"high", "critical"}:
        create_notification(
            db, notification_type="CRITICAL_REPORT", title=f"{result['risk_level']} safety report",
            message=f"{report.report_id} at {report.site} requires HSE attention.",
            entity_type="REPORT", entity_id=report.report_id,
            dedupe_key=f"critical-report:{report.report_id}", recipient_role="HSE_OFFICER",
            recipient_site=report.site,
        )
    if confidence["hse_review_recommended"]:
        create_notification(
            db, notification_type="LOW_CONFIDENCE_HIGH_RISK", title="HSE review recommended",
            message=f"High-consequence report {report.report_id} has low evidence confidence.",
            entity_type="REPORT", entity_id=report.report_id,
            dedupe_key=f"low-confidence:{report.report_id}", recipient_role="HSE_OFFICER",
            recipient_site=report.site,
        )
    for alert in alerts:
        notification_type = {
            "emerging_cluster": "EMERGING_SIF_PATTERN",
            "critical_control_acceleration": "CRITICAL_CONTROL_DETERIORATION",
        }.get(alert.alert_type)
        if notification_type:
            create_notification(
                db, notification_type=notification_type, title=alert.title,
                message=f"{report.site}: {result.get('precursor_pattern') or result.get('critical_control')}",
                entity_type="ALERT", entity_id=alert.alert_id,
                dedupe_key=f"analysis-alert:{alert.alert_id}", recipient_role="HSE_MANAGER",
                recipient_site=report.site,
            )
    if (result.get("pattern_status") or {}).get("state") == "new_pattern_alert":
        create_notification(
            db, notification_type="NEW_PRECURSOR_ESTABLISHED", title="New precursor candidate became established",
            message=f"A recurring unclassified precursor at {report.site} crossed the alert threshold.",
            entity_type="REPORT", entity_id=report.report_id,
            dedupe_key=f"new-pattern:{result['pattern_status'].get('label')}:{report.site}",
            recipient_role="HSE_MANAGER", recipient_site=report.site,
        )
    db.commit()
    return result


@app.get("/analysis/status")
def get_analysis_status(
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    sites = scoped_sites(actor)
    if sites is None:
        result = analysis_status(db)
    else:
        items = filtered_analyses(db, actor=actor)
        result = {
            "total_reports": len(items), "analysed": sum(item.status == "analysed" for item in items),
            "pending": sum(item.status == "pending" for item in items), "failed": sum(item.status == "failed" for item in items),
        }
    db.commit()
    return result


@app.post("/analysis/batch")
def run_batch_analysis(
    request: BatchAnalyzeRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "REVIEW_ANALYSIS")
    return batch_analyze(
        db,
        include_failed=request.include_failed,
        reanalyze_all=request.reanalyze_all,
        use_gemini=request.use_gemini,
        actor=actor,
        site_scope=actor.site_scope,
    )


@app.post("/jobs/historical-analysis", status_code=202)
def start_historical_analysis(
    request: BatchAnalyzeRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "REVIEW_ANALYSIS")
    job = create_job(db, actor, "HISTORICAL_ANALYSIS", {
        **request.model_dump(), "actor_name": actor.name, "actor_role": actor.role,
        "actor_user_id": actor.user_id, "site_scope": list(scoped_sites(actor) or ("*",)),
    })
    submit_persisted_job(db, job)
    return job_to_dict(job)


@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> list[dict]:
    query = db.query(BackgroundJob)
    sites = scoped_sites(actor)
    if actor.role == "WORKER" and actor.user_id:
        query = query.filter(BackgroundJob.created_by_user_id == actor.user_id)
    elif sites is not None:
        query = query.filter(
            (BackgroundJob.site.in_(sites)) |
            ((BackgroundJob.site.is_(None)) & (BackgroundJob.created_by_user_id == actor.user_id))
        )
    return [job_to_dict(item) for item in query.order_by(BackgroundJob.created_at.desc()).limit(100).all()]


@app.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    job = db.get(BackgroundJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.site:
        require_site(actor, job.site)
    elif scoped_sites(actor) is not None and job.created_by_user_id != actor.user_id:
        raise HTTPException(status_code=403, detail="Site-scoped accounts may only view their own unscoped jobs.")
    if actor.role == "WORKER" and actor.user_id != job.created_by_user_id:
        raise HTTPException(status_code=403, detail="Workers may only view their own jobs.")
    return job_to_dict(job)


@app.post("/jobs/ocr", status_code=202)
def start_ocr_job(
    file: UploadFile = File(...), site: str = Form(default=""), activity: str = Form(default=""),
    observed_at: str = Form(default=""),
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "SUBMIT_REPORT")
    if site:
        require_site(actor, site)
    content = file.file.read()
    safe_name = validate_file(
        file.filename or "scan.pdf", file.content_type or "application/pdf", content,
        allowed_extensions={".pdf"},
    )
    job = create_job(db, actor, "OCR_PROCESSING", site=site or None)
    attachment = save_attachment(
        db, actor, entity_type="JOB", entity_id=job.job_id, filename=safe_name,
        media_type=file.content_type or "application/pdf", content=content,
        description="Scanned report awaiting OCR", allowed_extensions={".pdf"},
    )
    job.payload = json.dumps({
        "attachment_id": attachment.attachment_id, "site": site, "activity": activity,
        "observed_at": observed_at, "actor_name": actor.name, "actor_role": actor.role,
        "actor_user_id": actor.user_id, "site_scope": list(actor.site_scope),
    })
    submit_persisted_job(db, job)
    return job_to_dict(job)


@app.post("/jobs/photo-analysis", status_code=202)
def start_photo_job(
    file: UploadFile = File(...), description: str = Form(default=""), site: str = Form(default=""),
    activity: str = Form(default=""), observed_at: str = Form(default=""),
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "SUBMIT_REPORT")
    if site:
        require_site(actor, site)
    content = file.file.read()
    safe_name = validate_file(
        file.filename or "photo.jpg", file.content_type or "application/octet-stream", content,
        allowed_extensions={".jpg", ".jpeg", ".png", ".webp"},
    )
    job = create_job(db, actor, "PHOTO_ANALYSIS", {"description": description}, site=site or None)
    attachment = save_attachment(
        db, actor, entity_type="JOB", entity_id=job.job_id, filename=safe_name,
        media_type=file.content_type or "", content=content,
        description="Photo awaiting visual evidence analysis",
        allowed_extensions={".jpg", ".jpeg", ".png", ".webp"},
    )
    job.payload = json.dumps({
        "attachment_id": attachment.attachment_id, "description": description, "site": site,
        "activity": activity, "observed_at": observed_at, "actor_name": actor.name,
        "actor_role": actor.role, "actor_user_id": actor.user_id, "site_scope": list(actor.site_scope),
    })
    submit_persisted_job(db, job)
    return job_to_dict(job)


@app.get("/notifications")
def list_notifications(
    unread: bool = False, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> list[dict]:
    query = unread_notification_query(db, actor) if unread else notification_query(db, actor)
    return [notification_to_dict(item, db, actor) for item in query.order_by(Notification.created_at.desc()).limit(200).all()]


@app.get("/notifications/unread-count")
def unread_notification_count(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    return {"unread": unread_notification_query(db, actor).count()}


@app.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    item = mark_read(db, actor, notification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    db.commit()
    return notification_to_dict(item, db, actor)


@app.post("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    count = mark_all_read(db, actor)
    db.commit()
    return {"marked_read": count}


@app.post("/reports/upload", response_model=UploadResponse)
def upload_reports(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> UploadResponse:
    # Dataset administration is restricted even though individual workers may submit observations.
    require(actor, "REVIEW_ANALYSIS")
    dataframe = read_uploaded_dataframe(file)
    validate_required_columns(dataframe)
    inserted = updated = unchanged = 0
    for row in dataframe[REQUIRED_COLUMNS].to_dict(orient="records"):
        payload = {COLUMN_MAPPING[column]: str(value).strip() for column, value in row.items()}
        require_site(actor, payload["site"])
        existing = db.get(SafetyReport, payload["report_id"])
        if existing is None:
            report = SafetyReport(**payload)
            report.analysis = HistoricalAnalysis(status="pending")
            db.add(report)
            append_audit(db, actor, "REPORT_SUBMITTED", "REPORT", payload["report_id"], new_value={"source": "dataset_upload", "description": payload["description"]})
            inserted += 1
            continue
        changed = any(str(getattr(existing, field) or "") != value for field, value in payload.items())
        if not changed:
            unchanged += 1
            continue
        old_value = {field: getattr(existing, field) for field in payload}
        for field, value in payload.items():
            setattr(existing, field, value)
        mark_analysis_pending(existing)
        append_audit(
            db, actor, "REPORT_SOURCE_UPDATED", "REPORT", existing.report_id,
            old_value=old_value, new_value=payload,
            reason="Changed source fields invalidated only this report's derived analysis.",
        )
        updated += 1
    db.commit()
    return UploadResponse(
        message="Safety dataset processed; changed records are pending analysis.",
        total_rows=len(dataframe.index), inserted=inserted, updated=updated, unchanged=unchanged,
    )


@app.post("/reports/upload-pdf", response_model=AnalyzeResponse)
def upload_pdf_report(
    file: UploadFile = File(...),
    site: str = Form(default=""), activity: str = Form(default=""),
    observed_at: str = Form(default=""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AnalyzeResponse:
    content = file.file.read()
    validate_file(file.filename or "report.pdf", file.content_type or "application/pdf", content, allowed_extensions={".pdf"})
    extraction = extract_pdf_with_fallback(content)
    parsed_observed = None
    if observed_at:
        try:
            parsed_observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="observed_at must be an ISO-8601 timestamp.") from exc
    result = analyze_report(
        AnalyzeRequest(description=extraction["text"], site=site, activity=activity, observed_at=parsed_observed),
        db=db, actor=actor,
    )
    result["document_extraction"] = {key: value for key, value in extraction.items() if key != "text"}
    quality = None
    if extraction["text_source"] == "ocr" and extraction.get("ocr_confidence") is not None:
        quality = "LOW" if extraction["ocr_confidence"] < 0.6 else "MEDIUM" if extraction["ocr_confidence"] < 0.85 else "HIGH"
    confidence = assess_confidence(
        description=extraction["text"], site=site, activity=activity, analysis=result,
        text_source=extraction["text_source"], input_quality=quality,
    )
    report = db.get(SafetyReport, result["report_id"])
    report.confidence_label = confidence["label"]
    report.confidence_reasons = json.dumps(confidence["reasons"])
    report.review_recommended = confidence["hse_review_recommended"]
    result["confidence"] = confidence
    result["hse_review_recommended"] = confidence["hse_review_recommended"]
    db.commit()
    return result


@app.post("/analyze/photo")
def analyze_photo_report(
    file: UploadFile = File(...), description: str = Form(default=""),
    site: str = Form(default=""), activity: str = Form(default=""), observed_at: str = Form(default=""),
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "SUBMIT_REPORT")
    if site:
        require_site(actor, site)
    content = file.file.read()
    safe_name = validate_file(
        file.filename or "photo.jpg", file.content_type or "application/octet-stream", content,
        allowed_extensions={".jpg", ".jpeg", ".png", ".webp"},
    )
    findings = analyze_photo(content, file.content_type or "", description)
    combined, provenance = combined_description(description, findings)
    parsed_observed = None
    if observed_at:
        try:
            parsed_observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="observed_at must be an ISO-8601 timestamp.") from exc
    result = analyze_report(
        AnalyzeRequest(description=combined, site=site, activity=activity, observed_at=parsed_observed),
        db=db, actor=actor,
    )
    report = db.get(SafetyReport, result["report_id"])
    confidence = assess_confidence(
        description=description, site=site, activity=activity, analysis=result,
        text_source="image", input_quality=findings["confidence"],
    )
    report.input_provenance = json.dumps(provenance)
    report.photo_findings = json.dumps(findings)
    report.confidence_label = confidence["label"]
    report.confidence_reasons = json.dumps(confidence["reasons"])
    report.review_recommended = confidence["hse_review_recommended"]
    attachment = save_attachment(
        db, actor, entity_type="REPORT", entity_id=report.report_id, filename=safe_name,
        media_type=file.content_type or "", content=content, description="Hazard observation photo",
        allowed_extensions={".jpg", ".jpeg", ".png", ".webp"},
    )
    photo_record = PhotoAnalysis(
        photo_analysis_id=f"IMG-{uuid4().hex[:16].upper()}", report_id=report.report_id,
        attachment_id=attachment.attachment_id,
        visible_hazards=json.dumps(findings["visible_hazards"]),
        visible_controls=json.dumps(findings["visible_controls"]),
        possible_missing_controls=json.dumps(findings["possible_missing_controls"]),
        possible_exposures=json.dumps(findings["possible_exposures"]),
        image_summary=findings["image_summary"], confidence=findings["confidence"], provider="gemini",
    )
    db.add(photo_record)
    if confidence["hse_review_recommended"]:
        create_notification(
            db, notification_type="LOW_CONFIDENCE_HIGH_RISK", title="HSE review recommended",
            message=f"High-consequence photo report {report.report_id} has low evidence confidence.",
            entity_type="REPORT", entity_id=report.report_id,
            dedupe_key=f"low-confidence:{report.report_id}", recipient_role="HSE_OFFICER",
            recipient_site=report.site,
        )
    append_audit(db, actor, "PHOTO_EVIDENCE_ATTACHED", "REPORT", report.report_id, new_value={"attachment_id": attachment.attachment_id})
    db.commit()
    result.update({
        "photo_findings": findings, "input_provenance": provenance, "confidence": confidence,
        "hse_review_recommended": confidence["hse_review_recommended"],
        "attachment": attachment_to_dict(attachment),
    })
    return result


@app.get("/roles/permissions")
def get_role_permissions() -> dict:
    return {"roles": permission_matrix()}


@app.post("/reports/{report_id}/reviews")
def review_report(
    report_id: str,
    request: ReviewCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "REVIEW_ANALYSIS")
    report = db.get(SafetyReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    require_site(actor, report.site)
    review = create_review(db, report, actor, request.model_dump())
    db.commit()
    db.refresh(review)
    return review_to_dict(review)


@app.get("/reports/{report_id}/reviewed-analysis")
def get_reviewed_analysis(
    report_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    report = db.get(SafetyReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    require_site(actor, report.site)
    review = latest_review(report)
    return {
        "report_id": report_id,
        "review_status": review.review_status if review else "unreviewed",
        "ai_analysis": {
            column.name: getattr(report.analysis, column.name)
            for column in HistoricalAnalysis.__table__.columns
            if column.name not in {"embedding"}
        } if report.analysis else None,
        "hse_reviewed_analysis": review_to_dict(review) if review else None,
        "review_history": [review_to_dict(item) for item in sorted(report.reviews, key=lambda row: row.created_at)],
    }


@app.get("/audit")
def list_audit_events(
    event_date: str = Query(default="", alias="date"), actor_filter: str = Query(default="", alias="actor"),
    role: str = "", event_type: str = Query(default="", alias="event_type"),
    report_id: str = "", capa_id: str = "", db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[dict]:
    require(actor, "AUDIT_VIEW")
    rows = query_audit(
        db, event_date=event_date, actor=actor_filter, role=role, event_type=event_type,
        report_id=report_id, capa_id=capa_id,
    )
    sites = scoped_sites(actor)
    if sites is None:
        return rows
    allowed_reports = {item.report_id for item in filtered_analyses(db, actor=actor)}
    allowed_capas = {item.capa_id for item in db.query(CAPA).all() if item.report_id in allowed_reports}
    return [
        row for row in rows
        if (row["entity_type"] == "REPORT" and row["entity_id"] in allowed_reports)
        or (row["entity_type"] == "CAPA" and row["entity_id"] in allowed_capas)
    ]


def _get_capa(db: Session, capa_id: str) -> CAPA:
    capa = db.get(CAPA, capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail="CAPA not found.")
    return capa


def _capa_site(db: Session, capa: CAPA) -> str | None:
    report = db.get(SafetyReport, capa.report_id) if capa.report_id else None
    return report.site if report else None


def _require_capa_scope(db: Session, actor: Actor, capa: CAPA) -> None:
    site = _capa_site(db, capa)
    if site:
        require_site(actor, site)
    elif scoped_sites(actor) is not None:
        raise HTTPException(status_code=403, detail="This CAPA is not linked to a site-scoped report.")


def _require_entity_scope(db: Session, actor: Actor, entity_type: str, entity_id: str) -> None:
    kind = entity_type.upper()
    if kind == "REPORT":
        report = db.get(SafetyReport, entity_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        require_site(actor, report.site)
    elif kind == "CAPA":
        capa = _get_capa(db, entity_id)
        _require_capa_scope(db, actor, capa)
    elif kind == "DOCUMENT":
        require(actor, "KNOWLEDGE_MANAGE")
        if db.get(SafetyDocument, entity_id) is None:
            raise HTTPException(status_code=404, detail="Safety document not found.")
    else:
        raise HTTPException(status_code=400, detail="Attachment entity must be REPORT, CAPA, or DOCUMENT.")


@app.post("/attachments")
def upload_attachment(
    file: UploadFile = File(...), entity_type: str = Form(...), entity_id: str = Form(...),
    description: str = Form(default=""), db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "CAPA_EVIDENCE")
    _require_entity_scope(db, actor, entity_type, entity_id)
    item = save_attachment(
        db, actor, entity_type=entity_type, entity_id=entity_id,
        filename=file.filename or "attachment", media_type=file.content_type or "application/octet-stream",
        content=file.file.read(), description=description,
    )
    append_audit(db, actor, "EVIDENCE_ATTACHMENT_ADDED", entity_type.upper(), entity_id, new_value=attachment_to_dict(item))
    db.commit()
    return attachment_to_dict(item)


@app.get("/attachments/{attachment_id}")
def get_attachment_metadata(
    attachment_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    item = db.get(Attachment, attachment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _require_entity_scope(db, actor, item.entity_type, item.entity_id)
    return attachment_to_dict(item)


@app.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
):
    item = db.get(Attachment, attachment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _require_entity_scope(db, actor, item.entity_type, item.entity_id)
    try:
        path = LocalFileStorage().path_for(item.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Attachment data is unavailable.") from exc
    return FileResponse(path, media_type=item.media_type, filename=item.filename)


@app.post("/capas/{capa_id}/evidence/upload")
def upload_capa_evidence(
    capa_id: str, file: UploadFile = File(...), note: str = Form(default="Evidence attachment"),
    description: str = Form(default=""), db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "CAPA_EVIDENCE")
    capa = _get_capa(db, capa_id)
    _require_entity_scope(db, actor, "CAPA", capa_id)
    attachment = save_attachment(
        db, actor, entity_type="CAPA", entity_id=capa_id, filename=file.filename or "evidence",
        media_type=file.content_type or "application/octet-stream", content=file.file.read(), description=description,
    )
    evidence = add_evidence(db, capa, actor, {"evidence_type": "attachment", "reference": attachment.attachment_id, "note": note})
    evidence.attachment_id = attachment.attachment_id
    db.commit()
    return {"evidence": {column.name: getattr(evidence, column.name) for column in evidence.__table__.columns}, "attachment": attachment_to_dict(attachment)}


@app.post("/capas")
def create_capa_endpoint(
    request: CAPACreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_CREATE")
    if request.report_id and db.get(SafetyReport, request.report_id) is None:
        raise HTTPException(status_code=404, detail="Linked report not found.")
    if request.report_id:
        require_site(actor, db.get(SafetyReport, request.report_id).site)
    if request.alert_id:
        linked_alert = db.get(SafetyAlert, request.alert_id)
        if linked_alert is None:
            raise HTTPException(status_code=404, detail="Linked alert not found.")
        if linked_alert.report:
            require_site(actor, linked_alert.report.site)
        elif scoped_sites(actor) is not None:
            raise HTTPException(status_code=403, detail="The linked alert has no site-scoped report.")
    capa = create_capa(db, actor, request.model_dump())
    if capa.owner_name:
        owner = db.query(User).filter(
            (User.username == capa.owner_name.strip().lower()) | (User.name == capa.owner_name.strip())
        ).first()
        create_notification(
            db, notification_type="CAPA_ASSIGNED", title="CAPA assigned",
            message=f"{capa.capa_id}: {capa.title}", entity_type="CAPA", entity_id=capa.capa_id,
            dedupe_key=f"capa-assigned:{capa.capa_id}:{capa.owner_name.casefold()}",
            recipient_user_id=owner.user_id if owner else None,
            recipient_role=capa.owner_role or "SITE_SUPERVISOR", recipient_site=_capa_site(db, capa),
        )
    db.commit()
    db.refresh(capa)
    return capa_to_dict(capa)


@app.get("/capas")
def list_capas(
    status: str = "", priority: str = "", owner: str = "", report_id: str = "",
    overdue: bool | None = Query(default=None), db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[dict]:
    query = db.query(CAPA)
    if status:
        query = query.filter(CAPA.status == status.lower())
    if priority:
        query = query.filter(CAPA.priority == priority.lower())
    if owner:
        query = query.filter(CAPA.owner_name.ilike(f"%{owner}%"))
    if report_id:
        query = query.filter(CAPA.report_id == report_id)
    items = query.order_by(CAPA.created_at.desc()).all()
    allowed = scoped_sites(actor)
    if allowed is not None:
        allowed_normalized = {item.casefold() for item in allowed}
        items = [item for item in items if (_capa_site(db, item) or "").casefold() in allowed_normalized]
    rows = [capa_to_dict(item) for item in items]
    for capa, row in zip(items, rows):
        if row["is_overdue"]:
            create_notification(
                db, notification_type="CAPA_OVERDUE", title="CAPA overdue",
                message=f"{capa.capa_id} is overdue and requires action.", entity_type="CAPA",
                entity_id=capa.capa_id, dedupe_key=f"capa-overdue:{capa.capa_id}",
                recipient_role=capa.owner_role or "SITE_SUPERVISOR", recipient_site=_capa_site(db, capa),
            )
    db.commit()
    return [row for row in rows if overdue is None or row["is_overdue"] is overdue]


@app.get("/capas/{capa_id}")
def get_capa_endpoint(
    capa_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    return capa_to_dict(capa)


@app.post("/capas/{capa_id}/assign")
def assign_capa_endpoint(
    capa_id: str, request: CAPAAssign, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_ASSIGN")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    capa = assign_capa(db, capa, actor, request.owner_name, request.owner_role)
    owner = db.query(User).filter(
        (User.username == request.owner_name.strip().lower()) | (User.name == request.owner_name.strip())
    ).first()
    create_notification(
        db, notification_type="CAPA_ASSIGNED", title="CAPA assigned",
        message=f"{capa.capa_id}: {capa.title}", entity_type="CAPA", entity_id=capa.capa_id,
        dedupe_key=f"capa-assigned:{capa.capa_id}:{request.owner_name.casefold()}",
        recipient_user_id=owner.user_id if owner else None, recipient_role=request.owner_role,
        recipient_site=_capa_site(db, capa),
    )
    db.commit()
    return capa_to_dict(capa)


@app.post("/capas/{capa_id}/status")
def update_capa_status(
    capa_id: str, request: CAPAStatusChange, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_UPDATE")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    capa = transition_capa(db, capa, actor, request.status, request.note)
    if capa.status == "awaiting_verification":
        create_notification(
            db, notification_type="CAPA_AWAITING_VERIFICATION", title="CAPA awaits verification",
            message=f"{capa.capa_id} is ready for independent verification.", entity_type="CAPA",
            entity_id=capa.capa_id, dedupe_key=f"capa-awaiting:{capa.capa_id}:{capa.completed_at}",
            recipient_role="HSE_OFFICER", recipient_site=_capa_site(db, capa),
        )
    db.commit()
    return capa_to_dict(capa)


@app.post("/capas/{capa_id}/evidence")
def add_capa_evidence(
    capa_id: str, request: CAPAEvidenceCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_EVIDENCE")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    item = add_evidence(db, capa, actor, request.model_dump())
    db.commit()
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


@app.post("/capas/{capa_id}/submit-verification")
def submit_capa_verification(
    capa_id: str, request: NoteRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_UPDATE")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    capa = transition_capa(db, capa, actor, "awaiting_verification", request.note)
    create_notification(
        db, notification_type="CAPA_AWAITING_VERIFICATION", title="CAPA awaits verification",
        message=f"{capa.capa_id} is ready for independent verification.", entity_type="CAPA",
        entity_id=capa.capa_id, dedupe_key=f"capa-awaiting:{capa.capa_id}:{capa.completed_at}",
        recipient_role="HSE_OFFICER", recipient_site=_capa_site(db, capa),
    )
    db.commit()
    return capa_to_dict(capa)


@app.post("/capas/{capa_id}/verify")
def verify_capa_endpoint(
    capa_id: str, request: NoteRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_VERIFY")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    capa = verify_closure(db, capa, actor, request.note)
    db.commit()
    return capa_to_dict(capa)


@app.post("/capas/{capa_id}/reopen")
def reopen_capa_endpoint(
    capa_id: str, request: NoteRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "CAPA_VERIFY")
    capa = _get_capa(db, capa_id)
    _require_capa_scope(db, actor, capa)
    capa = transition_capa(db, capa, actor, "reopened", request.note)
    db.commit()
    return capa_to_dict(capa)


@app.post("/knowledge/documents", status_code=202)
def upload_knowledge_document(
    file: UploadFile = File(...), title: str = Form(...), organization: str = Form(...),
    version: str = Form(default=""), effective_date: str = Form(default=""),
    source_reference: str = Form(default=""), review_date: str = Form(default=""),
    supersedes_document_id: str = Form(default=""), db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "KNOWLEDGE_MANAGE")
    content = file.file.read()
    safe_name = validate_file(
        file.filename or "document.txt", file.content_type or "application/octet-stream", content,
        allowed_extensions={".pdf", ".txt"},
    )
    if supersedes_document_id and db.get(SafetyDocument, supersedes_document_id) is None:
        raise HTTPException(status_code=404, detail="Document to supersede was not found.")
    document = SafetyDocument(
        document_id=f"DOC-{uuid4().hex[:12].upper()}", title=title.strip(), organization=organization.strip(),
        version=version.strip() or None, effective_date=effective_date.strip() or None,
        source_reference=source_reference.strip() or None, review_date=review_date.strip() or None,
        supersedes_document_id=supersedes_document_id or None, filename=safe_name,
        uploaded_by=actor.name, chunk_count=0, status="DRAFT", indexing_status="pending",
    )
    if not document.title or not document.organization:
        raise HTTPException(status_code=400, detail="Document title and organization are required.")
    db.add(document)
    db.flush()
    attachment = save_attachment(
        db, actor, entity_type="DOCUMENT", entity_id=document.document_id, filename=safe_name,
        media_type=file.content_type or "", content=content, description="Controlled source document",
        allowed_extensions={".pdf", ".txt"},
    )
    document.attachment_id = attachment.attachment_id
    job = create_job(db, actor, "DOCUMENT_INDEXING", {
        "document_id": document.document_id, "attachment_id": attachment.attachment_id,
        "actor_name": actor.name, "actor_role": actor.role, "actor_user_id": actor.user_id,
        "site_scope": list(actor.site_scope),
    })
    append_audit(db, actor, "KNOWLEDGE_DOCUMENT_DRAFT_CREATED", "DOCUMENT", document.document_id, new_value={"version": document.version})
    submit_persisted_job(db, job)
    return {"document": document_to_dict(document), "job": job_to_dict(job)}


@app.get("/knowledge/documents")
def list_knowledge_documents(
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> list[dict]:
    require(actor, "KNOWLEDGE_MANAGE")
    return [document_to_dict(item) for item in db.query(SafetyDocument).order_by(SafetyDocument.uploaded_at.desc()).all()]


@app.get("/knowledge/documents/{document_id}")
def get_knowledge_document(
    document_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "KNOWLEDGE_MANAGE")
    document = db.get(SafetyDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Safety document not found.")
    return document_to_dict(document, include_chunks=True)


@app.post("/knowledge/documents/{document_id}/approve")
def approve_knowledge_document(
    document_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "KNOWLEDGE_MANAGE")
    document = db.get(SafetyDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Safety document not found.")
    previous = db.get(SafetyDocument, document.supersedes_document_id) if document.supersedes_document_id else None
    transition_document(db, document, actor, "APPROVE", supersedes=previous)
    db.commit()
    return document_to_dict(document)


@app.post("/knowledge/documents/{document_id}/retire")
def retire_knowledge_document(
    document_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "KNOWLEDGE_MANAGE")
    document = db.get(SafetyDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Safety document not found.")
    transition_document(db, document, actor, "RETIRE")
    db.commit()
    return document_to_dict(document)


@app.get("/analytics/critical-controls")
def get_critical_control_health(
    date_from: str = "", date_to: str = "", site: str = "", department: str = "",
    activity: str = "", db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    items = filtered_analyses(db, date_from=date_from, date_to=date_to, site=site, department=department, activity=activity, actor=actor)
    return {"controls": critical_control_health(items), "filters_applied": {"date_from": date_from, "date_to": date_to, "site": site, "department": department, "activity": activity}}


@app.get("/analytics/hse-agreement")
def get_hse_agreement(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    require(actor, "AUDIT_VIEW")
    sites = scoped_sites(actor)
    report_ids = None if sites is None else {item.report_id for item in filtered_analyses(db, actor=actor)}
    return agreement_metrics(db, report_ids)


@app.post("/validation/datasets")
def upload_validation_dataset(
    file: UploadFile = File(...), name: str = Form(...), description: str = Form(default=""),
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "ANALYTICS_ADVANCED")
    content = file.file.read()
    validate_file(file.filename or "validation.csv", file.content_type or "text/csv", content, allowed_extensions={".csv"})
    try:
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, na_filter=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Validation CSV could not be parsed.") from exc
    missing = [column for column in GROUND_TRUTH_COLUMNS if column not in frame.columns]
    if missing:
        raise HTTPException(status_code=400, detail={"message": "Validation CSV is missing ground-truth columns.", "missing_columns": missing})
    dataset = ValidationDataset(
        dataset_id=f"VDS-{uuid4().hex[:16].upper()}", name=name.strip(),
        description=description.strip() or None, created_by=actor.name, case_count=len(frame.index),
    )
    if not dataset.name:
        raise HTTPException(status_code=400, detail="Validation dataset name is required.")
    db.add(dataset)
    for row in frame.to_dict(orient="records"):
        db.add(ValidationCase(
            case_id=f"VCS-{uuid4().hex[:16].upper()}", dataset_id=dataset.dataset_id,
            description=str(row["description"]).strip(), site=str(row.get("site", "")).strip() or None,
            activity=str(row.get("activity", "")).strip() or None,
            expected_hazard=str(row["expected_hazard"]).strip(),
            expected_exposure=str(row["expected_exposure"]).strip(),
            expected_critical_control=str(row["expected_critical_control"]).strip(),
            expected_precursor=str(row["expected_precursor"]).strip(),
            expected_risk_level=str(row["expected_risk_level"]).strip(),
        ))
    append_audit(db, actor, "VALIDATION_DATASET_LOADED", "VALIDATION_DATASET", dataset.dataset_id, new_value={"case_count": dataset.case_count})
    db.commit()
    return {"dataset_id": dataset.dataset_id, "name": dataset.name, "case_count": dataset.case_count, "created_at": dataset.created_at}


@app.post("/validation/datasets/{dataset_id}/run")
def execute_validation(
    dataset_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "ANALYTICS_ADVANCED")
    dataset = db.get(ValidationDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Validation dataset not found.")
    run = run_validation(db, dataset)
    append_audit(db, actor, "VALIDATION_RUN_COMPLETED", "VALIDATION_RUN", run.run_id, new_value=json.loads(run.metrics))
    db.commit()
    return run_to_dict(run)


@app.get("/validation/datasets")
def list_validation_datasets(
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> list[dict]:
    require(actor, "ANALYTICS_ADVANCED")
    return [
        {"dataset_id": item.dataset_id, "name": item.name, "description": item.description,
         "case_count": item.case_count, "created_by": item.created_by, "created_at": item.created_at}
        for item in db.query(ValidationDataset).order_by(ValidationDataset.created_at.desc()).all()
    ]


@app.get("/validation/runs")
def list_validation_runs(
    db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> list[dict]:
    require(actor, "ANALYTICS_ADVANCED")
    return [run_to_dict(item) for item in db.query(ValidationRun).order_by(ValidationRun.validation_timestamp.desc()).all()]


@app.get("/validation/runs/{run_id}")
def get_validation_run(
    run_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
) -> dict:
    require(actor, "ANALYTICS_ADVANCED")
    run = db.get(ValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found.")
    return run_to_dict(run)


@app.get("/alerts")
def list_alerts(
    status: str = "", severity: str = "", db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[dict]:
    require(actor, "ALERT_VIEW")
    query = db.query(SafetyAlert)
    if status:
        query = query.filter(SafetyAlert.status == status.lower())
    if severity:
        query = query.filter(SafetyAlert.severity == severity.lower())
    rows = query.order_by(SafetyAlert.created_at.desc()).all()
    sites = scoped_sites(actor)
    if sites is not None:
        allowed = {item.casefold() for item in sites}
        rows = [item for item in rows if item.report and str(item.report.site).casefold() in allowed]
    return [alert_to_dict(item) for item in rows]


@app.post("/alerts/{alert_id}/decision")
def alert_decision(
    alert_id: str, request: AlertDecisionRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> dict:
    require(actor, "ALERT_DECIDE")
    alert = db.get(SafetyAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.report:
        require_site(actor, alert.report.site)
    elif scoped_sites(actor) is not None:
        raise HTTPException(status_code=403, detail="This alert is not linked to a site-scoped report.")
    alert = decide_alert(db, alert, actor, request.decision, request.reason)
    if request.decision.strip().lower() == "escalate":
        create_notification(
            db, notification_type="ALERT_ESCALATION", title="Safety alert escalated",
            message=f"{alert.alert_id}: {alert.title}", entity_type="ALERT", entity_id=alert.alert_id,
            dedupe_key=f"alert-escalation:{alert.alert_id}", recipient_role="HSE_MANAGER",
            recipient_site=alert.report.site if alert.report else None,
        )
    db.commit()
    return alert_to_dict(alert)


@app.get("/reports/export.csv")
def export_reports_csv(
    date_from: str = "", date_to: str = "", site: str = "", department: str = "",
    activity: str = "", risk_level: str = "", precursor: str = "",
    cluster_id: int | None = Query(default=None), db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> StreamingResponse:
    items = filtered_analyses(
        db, date_from=date_from, date_to=date_to, site=site, department=department,
        activity=activity, risk_level=risk_level, precursor=precursor, cluster_id=cluster_id, actor=actor,
    )
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([label for label, _ in EXPORT_COLUMNS])
    for item in items:
        report_values = vars(item.report)
        analysis_values = vars(item)
        writer.writerow([report_values.get(field, analysis_values.get(field, "")) for _, field in EXPORT_COLUMNS])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sajag-report-export.csv"'},
    )


@app.get("/reports", response_model=list[SafetyReportResponse])
def list_reports(
    date_from: str = "", date_to: str = "", site: str = "", department: str = "",
    activity: str = "", risk_level: str = "", precursor: str = "",
    cluster_id: int | None = Query(default=None), db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[SafetyReport]:
    items = filtered_analyses(
        db, date_from=date_from, date_to=date_to, site=site, department=department,
        activity=activity, risk_level=risk_level, precursor=precursor, cluster_id=cluster_id, actor=actor,
    )
    return [item.report for item in items]


@app.get("/reports/{report_id}", response_model=SafetyReportResponse)
def get_report(
    report_id: str, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> SafetyReport:
    report = db.query(SafetyReport).options(joinedload(SafetyReport.analysis)).filter_by(report_id=report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    require_site(actor, report.site)
    if actor.role == "WORKER" and actor.user_id and report.submitted_by_user_id != actor.user_id:
        raise HTTPException(status_code=403, detail="Workers may only access their own reports.")
    return report


@app.get("/clusters")
def list_clusters(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> list[dict]:
    items = filtered_analyses(db, actor=actor)
    as_of = trend_anchor(items)
    emerging = {item["cluster_id"] for item in emerging_cluster_patterns(items)}
    grouped = {cluster["cluster_id"]: cluster for cluster in summarize_clusters(items)}
    for cluster_id, summary in grouped.items():
        members = [item for item in items if item.cluster_id == cluster_id]
        summary["trend"] = {**cluster_trend(members, as_of), "as_of_date": as_of.isoformat()}
        summary["emerging"] = cluster_id in emerging
    return list(grouped.values())


@app.get("/clusters/{cluster_id}")
def get_cluster(cluster_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    items = filtered_analyses(db, cluster_id=cluster_id, actor=actor)
    if not items or cluster_id < 0:
        raise HTTPException(status_code=404, detail="Established cluster not found. Noise is exposed as unclassified.")
    summary = summarize_clusters(items)[0]
    summary["trend"] = {**cluster_trend(items, trend_anchor(items)), "as_of_date": trend_anchor(items).isoformat()}
    summary["reports"] = [SafetyReportResponse.model_validate(item.report).model_dump(mode="json") for item in items]
    return summary


@app.get("/emerging-risks")
def get_emerging_risks(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    items = filtered_analyses(db, actor=actor)
    return {
        "alerts": emerging_cluster_patterns(items),
        "disclaimer": "SAJAG detects increasing precursor frequency; it does not predict fatalities with certainty.",
    }


@app.get("/analytics/trends")
def get_trends(
    date_from: str = "", date_to: str = "", site: str = "", department: str = "",
    activity: str = "", risk_level: str = "", precursor: str = "",
    cluster_id: int | None = Query(default=None), db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> dict:
    items = filtered_analyses(
        db, date_from=date_from, date_to=date_to, site=site, department=department,
        activity=activity, risk_level=risk_level, precursor=precursor, cluster_id=cluster_id, actor=actor,
    )
    return {**analytics_series(items), "site_metrics": site_metrics(items), "filters_applied": {
        "date_from": date_from, "date_to": date_to, "site": site, "department": department,
        "activity": activity, "risk_level": risk_level, "precursor": precursor, "cluster_id": cluster_id,
    }}


@app.get("/metrics/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> dict:
    scoped = filtered_analyses(db, actor=actor)
    unrestricted = scoped_sites(actor) is None
    result = dashboard_metrics(db) if unrestricted else _dashboard_from_items(scoped)
    result.update(governance_dashboard(db) if unrestricted else _scoped_governance_dashboard(db, scoped))
    result["hse_agreement"] = agreement_metrics(db, None if unrestricted else {item.report_id for item in scoped})
    controls = critical_control_health(scoped)
    result["most_deteriorating_critical_control"] = next(
        (item["critical_control"] for item in controls if item["trend"] == "worsening"),
        controls[0]["critical_control"] if controls else "Not available",
    )
    result["phase3a"] = {
        "pending_jobs": sum(item["status"] in {"queued", "running"} for item in list_jobs(db=db, actor=actor)),
        "failed_jobs": sum(item["status"] == "failed" for item in list_jobs(db=db, actor=actor)),
        "unread_critical_notifications": unread_notification_query(db, actor).filter(
            Notification.notification_type.in_(["CRITICAL_REPORT", "LOW_CONFIDENCE_HIGH_RISK"]),
        ).count(),
        "low_confidence_high_critical": sum(
            item.report.confidence_label == "LOW" and str(item.risk_level).lower() in {"high", "critical"}
            for item in scoped
        ),
        "documents": {
            "approved": db.query(SafetyDocument).filter(SafetyDocument.status == "APPROVED").count(),
            "draft": db.query(SafetyDocument).filter(SafetyDocument.status == "DRAFT").count(),
            "superseded": db.query(SafetyDocument).filter(SafetyDocument.status == "SUPERSEDED").count(),
            "retired": db.query(SafetyDocument).filter(SafetyDocument.status == "RETIRED").count(),
            "review_due": db.query(SafetyDocument).filter(
                SafetyDocument.status == "APPROVED", SafetyDocument.review_date.is_not(None),
                SafetyDocument.review_date <= date.today().isoformat(),
            ).count(),
        } if has_permission(actor, "KNOWLEDGE_MANAGE") else {"approved": 0, "draft": 0, "superseded": 0, "retired": 0, "review_due": 0},
        "validation": run_to_dict(db.query(ValidationRun).order_by(ValidationRun.validation_timestamp.desc()).first())
        if db.query(ValidationRun).count() else None,
    }
    db.commit()
    return result
