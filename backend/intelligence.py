import json
from collections import Counter
from pathlib import Path
import re
from typing import Any

import numpy as np
from dotenv import dotenv_values, load_dotenv
from fastapi import HTTPException
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity


load_dotenv(Path(__file__).with_name(".env"))
ENV_FILE = Path(__file__).with_name(".env")

MODEL_NAME = "gemini-2.5-flash"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_ANALYSIS_FIELDS = (
    "hazard",
    "energy_source",
    "exposure_type",
    "unsafe_act",
    "unsafe_condition",
    "critical_control",
    "control_status",
    "potential_consequence",
    "likelihood",
    "precursor_pattern",
    "life_saving_rule",
)
_gemini_client: genai.Client | None = None
_embedding_model: SentenceTransformer | None = None


class IntelligenceError(Exception):
    """An expected, user-facing intelligence-layer failure."""


def _gemini() -> genai.Client:
    global _gemini_client
    api_key = dotenv_values(ENV_FILE).get("GEMINI_API_KEY", "")
    api_key = api_key.strip() if isinstance(api_key, str) else ""
    if not api_key:
        raise IntelligenceError(
            "GEMINI_API_KEY is missing. Add GEMINI_API_KEY to backend/.env."
        )
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _embedder() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def gemini_analysis(description: str) -> dict[str, str]:
    prompt = f"""Analyze this workplace safety observation and return only the requested structured fields as JSON.
Description: {description}

Requirements:
- Do not generate any numeric score.
- Use concise, plain safety language.
- energy_source should identify the dominant hazardous energy or exposure source.
- exposure_type should describe the worker exposure such as struck-by, fall, caught-in, electrical contact, chemical inhalation, fire/explosion, pressure release, ergonomic strain, slip/trip.
- control_status should be a short label such as intact, degraded, missing, bypassed, failed, or unknown.
- potential_consequence should describe the reasonably credible worst outcome, such as minor injury, recordable injury, serious injury, permanent disability, single fatality, or multiple fatalities.
- likelihood should be one of: low, medium, high.
"""
    try:
        response = _gemini().models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {field: {"type": "string"} for field in _ANALYSIS_FIELDS},
                    "required": list(_ANALYSIS_FIELDS),
                },
            ),
        )
        parsed = json.loads(response.text or "{}")
    except IntelligenceError:
        raise
    except Exception as exc:
        raise IntelligenceError(f"Gemini analysis failed: {exc}") from exc

    return {field: str(parsed.get(field, "")).strip() for field in _ANALYSIS_FIELDS}


def _embedding_text(description: str, analysis: dict[str, str]) -> str:
    return " ".join([description, analysis.get("hazard", ""), analysis.get("precursor_pattern", "")])


def _similar_reports(description: str, stored_reports: list[Any], analysis: dict[str, str]) -> list[dict[str, Any]]:
    if not stored_reports:
        return []
    texts = [report.description for report in stored_reports]
    vectors = _embedder().encode(
        [_embedding_text(text, {}) for text in texts] + [_embedding_text(description, analysis)],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    scores = cosine_similarity(vectors[-1:], vectors[:-1])[0]
    ranked = np.argsort(scores)[::-1][:5]
    return [
        {
            "report_id": str(stored_reports[index].report_id),
            "description": str(stored_reports[index].description),
            "similarity": round(float(scores[index]), 4),
        }
        for index in ranked
    ]


def _cluster_label(description: str, stored_reports: list[Any], analysis: dict[str, str]) -> int:
    texts = [report.description for report in stored_reports] + [description]
    vectors = _embedder().encode(
        [_embedding_text(text, {}) for text in texts[:-1]] + [_embedding_text(description, analysis)],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    if len(vectors) < 2:
        return -1
    labels = DBSCAN(eps=0.35, min_samples=2, metric="cosine").fit_predict(vectors)
    return int(labels[-1])


def _site_activity_rankings(stored_reports: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    total = max(len(stored_reports), 1)
    site_counts = Counter(str(report.site) for report in stored_reports if report.site)
    activity_counts = Counter(str(report.activity) for report in stored_reports if report.activity)
    sites = [
        {"name": name, "precursor_density": round(count / total, 4), "rank": rank}
        for rank, (name, count) in enumerate(site_counts.most_common(), start=1)
    ]
    activities = [
        {"name": name, "precursor_density": round(count / total, 4), "rank": rank}
        for rank, (name, count) in enumerate(activity_counts.most_common(), start=1)
    ]
    return sites, activities


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _text_contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _score_potential_consequence(analysis: dict[str, str]) -> int:
    text = " ".join(
        [
            analysis.get("potential_consequence", ""),
            analysis.get("hazard", ""),
            analysis.get("exposure_type", ""),
        ]
    ).lower()

    if _text_contains_any(text, ("multiple fatalities", "catastrophic", "mass casualty")):
        return 30
    if _text_contains_any(
        text,
        ("fatality", "single fatality", "death", "permanent disability", "amputation"),
    ):
        return 26
    if _text_contains_any(
        text,
        ("serious injury", "major injury", "life-altering", "fracture", "severe burn"),
    ):
        return 20
    if _text_contains_any(
        text,
        ("recordable", "medical treatment", "lost time", "moderate injury"),
    ):
        return 12
    if _text_contains_any(text, ("minor injury", "first aid", "minor harm")):
        return 5
    return 10


def _score_hazardous_energy_exposure(analysis: dict[str, str]) -> int:
    text = " ".join(
        [
            analysis.get("hazard", ""),
            analysis.get("energy_source", ""),
            analysis.get("exposure_type", ""),
            analysis.get("potential_consequence", ""),
        ]
    ).lower()
    exposure_text = analysis.get("exposure_type", "").lower()

    direct_exposure = _text_contains_any(
        exposure_text,
        (
            "fall",
            "struck",
            "caught",
            "electrical",
            "inhalation",
            "fire",
            "explosion",
            "pressure",
            "contact",
            "engulfment",
        ),
    )

    if _text_contains_any(
        text,
        (
            "work at height",
            "fall from height",
            "suspended load",
            "line of fire",
            "confined space",
            "electrical",
            "energized",
            "high voltage",
            "arc flash",
            "vehicle impact",
            "mobile equipment",
            "crane",
            "explosion",
            "fire",
            "flammable",
            "pressure release",
            "stored pressure",
            "chemical release",
            "toxic gas",
            "asphyxiation",
        ),
    ):
        return 25 if direct_exposure else 22

    if _text_contains_any(
        text,
        (
            "moving machinery",
            "rotating equipment",
            "pinch point",
            "sharp edge",
            "manual handling",
            "hot surface",
            "slip",
            "trip",
        ),
    ):
        return 15 if direct_exposure else 12

    if text.strip():
        return 8

    return 0


def _score_critical_control_failure(analysis: dict[str, str]) -> int:
    control_text = analysis.get("critical_control", "").lower()
    status_text = analysis.get("control_status", "").lower()
    combined = f"{control_text} {status_text}".strip()

    if not combined:
        return 0
    if _text_contains_any(status_text, ("missing", "bypassed", "failed", "disabled", "not used", "absent")):
        return 25
    if _text_contains_any(status_text, ("degraded", "ineffective", "inadequate", "partial", "damaged")):
        return 18
    if _text_contains_any(status_text, ("unknown", "unclear", "not verified")):
        return 10
    if _text_contains_any(status_text, ("intact", "available", "effective", "in place", "functional")):
        return 4
    return 12


def _score_likelihood(analysis: dict[str, str]) -> int:
    likelihood_text = analysis.get("likelihood", "").lower()
    observation_text = " ".join(
        [
            analysis.get("unsafe_act", ""),
            analysis.get("unsafe_condition", ""),
            analysis.get("exposure_type", ""),
        ]
    ).lower()

    if "high" in likelihood_text or _text_contains_any(
        observation_text,
        ("ongoing exposure", "directly exposed", "under suspended load", "open edge", "energized"),
    ):
        return 10
    if "medium" in likelihood_text or _text_contains_any(
        observation_text,
        ("intermittent exposure", "near miss", "adjacent exposure", "possible contact"),
    ):
        return 6
    if "low" in likelihood_text:
        return 2
    return 4


def _score_historical_recurrence(similar_reports: list[dict[str, Any]]) -> int:
    recurrent_reports = [
        report for report in similar_reports if float(report.get("similarity", 0.0)) >= 0.55
    ]

    if len(recurrent_reports) >= 4:
        return 10
    if len(recurrent_reports) >= 2:
        return 7
    if len(recurrent_reports) == 1:
        return 4
    if similar_reports and max(float(report.get("similarity", 0.0)) for report in similar_reports) >= 0.45:
        return 2
    return 0


def _score_breakdown(
    analysis: dict[str, str],
    similar_reports: list[dict[str, Any]],
) -> dict[str, int]:
    potential_consequence = _score_potential_consequence(analysis)
    hazardous_energy_exposure = _score_hazardous_energy_exposure(analysis)
    critical_control_failure = _score_critical_control_failure(analysis)
    likelihood = _score_likelihood(analysis)
    historical_recurrence = _score_historical_recurrence(similar_reports)
    total = (
        potential_consequence
        + hazardous_energy_exposure
        + critical_control_failure
        + likelihood
        + historical_recurrence
    )

    return {
        "potential_consequence": potential_consequence,
        "hazardous_energy_exposure": hazardous_energy_exposure,
        "critical_control_failure": critical_control_failure,
        "likelihood": likelihood,
        "historical_recurrence": historical_recurrence,
        "total": total,
    }


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def analyze_description(
    description: str,
    site: str,
    activity: str,
    stored_reports: list[Any],
) -> dict[str, Any]:
    if not description.strip():
        raise HTTPException(status_code=400, detail="Description must not be empty.")
    try:
        analysis = gemini_analysis(description)
        similar_reports = _similar_reports(description, stored_reports, analysis)
        _cluster_label(description, stored_reports, analysis)
        _site_activity_rankings(stored_reports)
        score_breakdown = _score_breakdown(analysis, similar_reports)
    except IntelligenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "sif_score": float(score_breakdown["total"]),
        "risk_level": _risk_level(score_breakdown["total"]),
        "score_breakdown": score_breakdown,
        **{
            field: _normalize_text(analysis[field]) if field == "likelihood" else analysis[field]
            for field in _ANALYSIS_FIELDS
        },
        "similar_reports": similar_reports,
        "site": site,
        "activity": activity,
    }
