import re
from collections import Counter
from typing import Any

import numpy as np

from services.config import (
    SIMILARITY_RESULT_MIN_SCORE,
    SIMILARITY_WEIGHTS,
    SIMILAR_RESULTS_LIMIT,
)
from services.embeddings import cosine_score, deserialize_embedding


FIELD_COMPONENTS = {
    "hazard_match": "hazard",
    "energy_source_match": "energy_source",
    "exposure_match": "exposure_type",
    "critical_control_match": "critical_control",
    "precursor_match": "precursor_pattern",
}


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def categorical_match(left: Any, right: Any) -> float:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    left_tokens, right_tokens = set(a.split()), set(b.split())
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = overlap / union if union else 0.0
    containment = overlap / min(len(left_tokens), len(right_tokens)) if overlap else 0.0
    return min(1.0, 0.6 * containment + 0.4 * jaccard)


def preferred_embedding_model(analyses: list[Any]) -> str | None:
    counts = Counter(
        str(item.embedding_model)
        for item in analyses
        if getattr(item, "status", "") == "analysed" and getattr(item, "embedding_model", None)
    )
    return counts.most_common(1)[0][0] if counts else None


def rank_similar_reports(
    query_analysis: dict[str, str],
    query_embedding: np.ndarray,
    stored_analyses: list[Any],
    limit: int = SIMILAR_RESULTS_LIMIT,
    embedding_model: str | None = None,
    minimum_score: float = SIMILARITY_RESULT_MIN_SCORE,
) -> list[dict[str, Any]]:
    """Rank persisted reports and suppress content-identical evidence cards."""

    ranked: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in stored_analyses:
        report = getattr(item, "report", None)
        report_id = str(getattr(item, "report_id", ""))
        vector = deserialize_embedding(getattr(item, "embedding", None))
        if not report or not report_id or report_id in seen_ids or vector is None:
            continue
        if embedding_model and getattr(item, "embedding_model", None) != embedding_model:
            continue
        if vector.shape != query_embedding.shape:
            continue
        seen_ids.add(report_id)
        components = {"semantic_similarity": cosine_score(query_embedding, vector)}
        for component, field in FIELD_COMPONENTS.items():
            components[component] = categorical_match(query_analysis.get(field), getattr(item, field, ""))
        overall = sum(components[name] * weight for name, weight in SIMILARITY_WEIGHTS.items())
        if overall < minimum_score:
            continue
        reasons = build_match_reasons(components, item)
        ranked.append(
            {
                "report_id": report_id,
                "date": str(getattr(report, "date", "") or ""),
                "site": str(getattr(report, "site", "") or getattr(report, "location_site", "") or ""),
                "activity": str(getattr(report, "activity", "") or ""),
                "description": str(getattr(report, "description", "") or ""),
                "overall_match_percent": round(overall * 100, 1),
                "similarity": round(overall, 4),
                **{name: round(value * 100, 1) for name, value in components.items()},
                "match_reasons": reasons,
            }
        )

    ranked.sort(
        key=lambda row: (
            -row["overall_match_percent"],
            -row["semantic_similarity"],
            row["report_id"],
        )
    )

    # The supplied workbook repeats only ten descriptions across 100 IDs. Showing five
    # copies is technically five rows but provides no additional evidence to an HSE user.
    diverse: list[dict[str, Any]] = []
    seen_descriptions: set[str] = set()
    for row in ranked:
        fingerprint = normalize_text(row["description"])
        if fingerprint and fingerprint in seen_descriptions:
            continue
        seen_descriptions.add(fingerprint)
        diverse.append(row)
        if len(diverse) >= limit:
            break
    return diverse


def build_match_reasons(components: dict[str, float], item: Any) -> list[str]:
    candidates = []
    labels = {
        "precursor_match": ("Same precursor", "precursor_pattern"),
        "critical_control_match": ("Same critical-control failure", "critical_control"),
        "exposure_match": ("Same exposure", "exposure_type"),
        "hazard_match": ("Same hazard family", "hazard"),
        "energy_source_match": ("Same energy source", "energy_source"),
    }
    for key, (label, field) in labels.items():
        if components[key] >= 0.58:
            candidates.append((components[key], f"{label}: {getattr(item, field, '')}"))
    if components["semantic_similarity"] >= 0.2:
        candidates.append(
            (
                components["semantic_similarity"],
                f"Similar description: {round(components['semantic_similarity'] * 100)}%",
            )
        )
    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return [reason for _, reason in candidates[:4]] or ["Related safety context identified"]
