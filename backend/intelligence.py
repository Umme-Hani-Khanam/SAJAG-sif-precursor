import json
import os
from collections import Counter
from pathlib import Path
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
SCORE_WEIGHTS = {
    "severity": 0.40,
    "precursor_potential": 0.30,
    "pattern_frequency": 0.20,
    "trend": 0.10,
}
_ANALYSIS_FIELDS = (
    "hazard",
    "unsafe_act",
    "unsafe_condition",
    "activity",
    "sif_potential",
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
    prompt = f"""Analyze this workplace safety observation. Return only the requested structured fields.
Description: {description}

Use concise strings. sif_potential must be one of: low, medium, high.
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


def _sif_score(analysis: dict[str, str], similar_reports: list[dict[str, Any]], stored_reports: list[Any]) -> float:
    text = " ".join(analysis.values()).lower()
    severity = 100 if any(word in text for word in ("fatal", "life-threatening", "critical")) else 70 if any(word in text for word in ("high", "serious", "major")) else 40
    potential = {"high": 100, "medium": 60, "low": 20}.get(analysis.get("sif_potential", "").lower(), 40)
    frequency = min(100, len(similar_reports) * 20)
    trend = min(100, (len(stored_reports) / 100) * 100)
    return round(
        severity * SCORE_WEIGHTS["severity"]
        + potential * SCORE_WEIGHTS["precursor_potential"]
        + frequency * SCORE_WEIGHTS["pattern_frequency"]
        + trend * SCORE_WEIGHTS["trend"],
        2,
    )


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
        score = _sif_score(analysis, similar_reports, stored_reports)
    except IntelligenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "sif_score": score,
        "risk_level": "high" if score >= 70 else "medium" if score >= 40 else "low",
        **{field: analysis[field] for field in ("hazard", "unsafe_act", "unsafe_condition", "precursor_pattern", "life_saving_rule")},
        "similar_reports": similar_reports,
        "site": site,
        "activity": activity,
    }
