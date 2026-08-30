"""Backward-compatible facade for the refactored intelligence services."""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from services.extraction import heuristic_analysis
from services.pipeline import analyze_observation
from services.scoring import risk_level as _risk_level
from services.scoring import score_analysis as _score_breakdown


def analyze_description(
    description: str,
    site: str,
    activity: str,
    stored_reports=None,
    db: Session | None = None,
    site_scope: tuple[str, ...] | None = None,
    observed_at: datetime | None = None,
):
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="The persistent analysis pipeline requires a database session.",
        )
    try:
        return analyze_observation(
            description, site, activity, db, site_scope=site_scope, observed_at=observed_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
