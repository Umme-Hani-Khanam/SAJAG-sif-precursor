"""Persisted job abstraction with a replaceable in-process executor."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import BackgroundJob
from services.roles import Actor


JobHandler = Callable[[Session, dict, Callable[[int, int], None]], dict | None]
_HANDLERS: dict[str, JobHandler] = {}
logger = logging.getLogger("uvicorn.error")
INTERRUPTED_MESSAGE = "Interrupted by application restart; safe to retry."


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


def recover_interrupted_jobs(db: Session) -> int:
    """Fail jobs left non-terminal by an earlier API process."""

    jobs = db.query(BackgroundJob).filter(BackgroundJob.status.in_(("queued", "running"))).all()
    recovered_at = datetime.now(timezone.utc)
    for job in jobs:
        previous = job.status
        job.status = "failed"
        job.error = INTERRUPTED_MESSAGE
        job.completed_at = recovered_at
        logger.warning(
            "Recovered interrupted job job_id=%s job_type=%s previous_status=%s",
            job.job_id, job.job_type, previous,
        )
    if jobs:
        db.commit()
    return len(jobs)


def execute_job(db: Session, job: BackgroundJob, handler: JobHandler | None = None) -> BackgroundJob:
    handler = handler or _HANDLERS.get(job.job_type)
    job.status, job.started_at, job.error = "running", datetime.now(timezone.utc), None
    db.commit()

    def progress(current: int, total: int) -> None:
        current, total = max(0, int(current)), max(0, int(total))
        if db.get_bind() is not engine or engine.dialect.name == "sqlite":
            # Isolated tests do not share SessionLocal. SQLite cannot accept a
            # second writer while the analysis transaction holds its write lock.
            job.progress_current = min(current, total) if total else current
            job.progress_total = total
            db.commit()
            return
        progress_db = SessionLocal()
        try:
            persisted_job = progress_db.get(BackgroundJob, job.job_id)
            if persisted_job is not None:
                persisted_job.progress_current = min(current, total) if total else current
                persisted_job.progress_total = total
                progress_db.commit()
                db.expire(job, ["progress_current", "progress_total"])
                return
        finally:
            progress_db.close()

        raise RuntimeError(f"Persisted job {job.job_id} disappeared while reporting progress.")

    try:
        if handler is None:
            raise RuntimeError(f"No handler is registered for {job.job_type}.")
        result = handler(db, json.loads(job.payload or "{}"), progress) or {}
        db.refresh(job)
        job.result = json.dumps(result, default=str)
        job.status = "completed"
        if job.job_type == "HISTORICAL_ANALYSIS" and job.progress_total == 100 and job.progress_current >= 99:
            job.progress_current = job.progress_total = 100
        elif not job.progress_total:
            job.progress_current = job.progress_total = 1
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        if job.job_type == "HISTORICAL_ANALYSIS":
            logger.info("Historical job completed job_id=%s", job.job_id)
        else:
            logger.info("Job completed job_id=%s job_type=%s", job.job_id, job.job_type)
    except Exception as exc:
        db.rollback()
        job = db.get(BackgroundJob, job.job_id)
        if job is None:
            raise
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {str(exc)}"[:1000]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        if job.job_type == "HISTORICAL_ANALYSIS":
            logger.exception("Historical job failed job_id=%s", job.job_id)
        else:
            logger.exception("Job failed job_id=%s job_type=%s", job.job_id, job.job_type)
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
