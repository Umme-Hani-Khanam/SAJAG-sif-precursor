"""Persisted job abstraction with a replaceable in-process executor."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from database import SessionLocal
from models import BackgroundJob
from services.roles import Actor


JobHandler = Callable[[Session, dict, Callable[[int, int], None]], dict | None]
_HANDLERS: dict[str, JobHandler] = {}


def register_handler(job_type: str, handler: JobHandler) -> None:
    _HANDLERS[job_type.upper()] = handler


def job_to_dict(job: BackgroundJob) -> dict:
    return {
        "job_id": job.job_id, "job_type": job.job_type, "status": job.status,
        "progress_current": job.progress_current, "progress_total": job.progress_total,
        "progress_percent": round(job.progress_current * 100 / job.progress_total) if job.progress_total else 0,
        "result": json.loads(job.result) if job.result else None, "error": job.error,
        "site": job.site, "created_at": job.created_at, "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


def create_job(db: Session, actor: Actor, job_type: str, payload: dict | None = None, *, site: str | None = None) -> BackgroundJob:
    normalized = job_type.upper()
    if normalized not in {"HISTORICAL_ANALYSIS", "DOCUMENT_INDEXING", "OCR_PROCESSING", "PHOTO_ANALYSIS", "VALIDATION"}:
        raise ValueError(f"Unsupported job type: {normalized}")
    job = BackgroundJob(
        job_id=f"JOB-{uuid4().hex[:16].upper()}", job_type=normalized, status="queued",
        progress_current=0, progress_total=0, payload=json.dumps(payload or {}),
        created_by_user_id=actor.user_id, created_by_name=actor.name, site=site,
    )
    db.add(job)
    db.flush()
    return job


def execute_job(db: Session, job: BackgroundJob, handler: JobHandler | None = None) -> BackgroundJob:
    handler = handler or _HANDLERS.get(job.job_type)
    job.status, job.started_at, job.error = "running", datetime.now(timezone.utc), None
    db.commit()

    def progress(current: int, total: int) -> None:
        job.progress_current, job.progress_total = current, total
        db.commit()

    try:
        if handler is None:
            raise RuntimeError(f"No handler is registered for {job.job_type}.")
        result = handler(db, json.loads(job.payload or "{}"), progress) or {}
        job.result = json.dumps(result, default=str)
        job.status = "completed"
        if not job.progress_total:
            job.progress_current = job.progress_total = 1
    except Exception as exc:
        db.rollback()
        job = db.get(BackgroundJob, job.job_id)
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {str(exc)}"[:1000]
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return job


class JobExecutor:
    def submit(self, job_id: str) -> None:
        raise NotImplementedError


class InProcessJobExecutor(JobExecutor):
    def __init__(self, workers: int = 2):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sajag-job")

    def submit(self, job_id: str) -> None:
        self.pool.submit(self._run, job_id)

    @staticmethod
    def _run(job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(BackgroundJob, job_id)
            if job:
                execute_job(db, job)
        finally:
            db.close()


EXECUTOR = InProcessJobExecutor(max(1, int(os.getenv("JOB_WORKERS", "2"))))


def submit_persisted_job(db: Session, job: BackgroundJob) -> None:
    db.commit()
    if os.getenv("JOB_EXECUTION_MODE", "thread").lower() == "eager":
        execute_job(db, job)
    else:
        EXECUTOR.submit(job.job_id)
