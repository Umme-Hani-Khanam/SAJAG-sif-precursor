from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from services.config import CLUSTER_ASSIGNMENT_MIN_SIMILARITY, DBSCAN_EPS, DBSCAN_MIN_SAMPLES
from services.embeddings import cosine_score, deserialize_embedding


def dbscan_cosine(
    vectors: np.ndarray,
    eps: float = DBSCAN_EPS,
    min_samples: int = DBSCAN_MIN_SAMPLES,
) -> np.ndarray:
    """Small deterministic DBSCAN implementation using cosine distance."""

    size = len(vectors)
    if not size:
        return np.asarray([], dtype=int)
    normalized = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    distances = 1.0 - np.clip(normalized @ normalized.T, -1.0, 1.0)
    neighborhoods = [np.flatnonzero(distances[index] <= eps).tolist() for index in range(size)]
    unvisited, noise = -99, -1
    labels = np.full(size, unvisited, dtype=int)
    cluster_id = 0
    for point in range(size):
        if labels[point] != unvisited:
            continue
        neighbors = neighborhoods[point]
        if len(neighbors) < min_samples:
            labels[point] = noise
            continue
        labels[point] = cluster_id
        queue = list(neighbors)
        queued = set(queue)
        cursor = 0
        while cursor < len(queue):
            candidate = queue[cursor]
            cursor += 1
            if labels[candidate] == noise:
                labels[candidate] = cluster_id
            if labels[candidate] != unvisited:
                continue
            labels[candidate] = cluster_id
            candidate_neighbors = neighborhoods[candidate]
            if len(candidate_neighbors) >= min_samples:
                for neighbor in candidate_neighbors:
                    if neighbor not in queued:
                        queued.add(neighbor)
                        queue.append(neighbor)
        cluster_id += 1
    labels[labels == unvisited] = noise
    return labels


def cluster_analyses(analyses: list[Any]) -> dict[str, int]:
    valid = []
    for item in sorted(analyses, key=lambda value: str(value.report_id)):
        vector = deserialize_embedding(item.embedding)
        if getattr(item, "status", "") == "analysed" and vector is not None:
            valid.append((item, vector))
    if not valid:
        return {}

    # Embeddings from different model versions are not put in the same metric space.
    assignments: dict[str, int] = {}
    offset = 0
    models = sorted({str(item.embedding_model) for item, _ in valid})
    for model in models:
        group = [(item, vector) for item, vector in valid if str(item.embedding_model) == model]
        dimensions = Counter(vector.shape for _, vector in group).most_common(1)[0][0]
        group = [(item, vector) for item, vector in group if vector.shape == dimensions]
        labels = dbscan_cosine(np.vstack([vector for _, vector in group]))
        non_noise = sorted(set(int(value) for value in labels if int(value) >= 0))
        remap = {label: offset + index for index, label in enumerate(non_noise)}
        for (item, _), label in zip(group, labels):
            assignments[str(item.report_id)] = -1 if int(label) < 0 else remap[int(label)]
        offset += len(non_noise)
    return assignments


def dominant(items: list[Any], field: str, fallback: str = "Not identified") -> str:
    values = [str(getattr(item, field, "") or "").strip() for item in items]
    values = [value for value in values if value]
    return Counter(values).most_common(1)[0][0] if values else fallback


def cluster_name(items: list[Any]) -> str:
    precursor = dominant(items, "precursor_pattern", "")
    if precursor:
        return precursor
    return f"{dominant(items, 'hazard')} / {dominant(items, 'exposure_type')}"


def summarize_clusters(analyses: list[Any]) -> list[dict]:
    grouped: dict[int, list[Any]] = {}
    for item in analyses:
        cluster_id = getattr(item, "cluster_id", None)
        if getattr(item, "status", "") == "analysed" and cluster_id is not None and cluster_id >= 0:
            grouped.setdefault(cluster_id, []).append(item)
    summaries = []
    for cluster_id in sorted(grouped):
        items = grouped[cluster_id]
        raw_dates = [_report_date_text(item.report) for item in items if item.report]
        raw_dates = [value for value in raw_dates if value]
        dates = [value for _, value in sorted((_date_sort_key(value), value) for value in raw_dates)]
        sites = sorted({str(item.report.site or item.report.location_site) for item in items if item.report})
        activities = sorted({str(item.report.activity) for item in items if item.report and item.report.activity})
        summaries.append(
            {
                "cluster_id": cluster_id,
                "cluster_code": f"C-{cluster_id + 1:02d}",
                "cluster_name": cluster_name(items),
                "report_count": len(items),
                "first_seen": dates[0] if dates else "",
                "last_seen": dates[-1] if dates else "",
                "latest_report_date": dates[-1] if dates else "",
                "sites_affected": sites,
                "activities_affected": activities,
                "dominant_hazard": dominant(items, "hazard"),
                "dominant_energy_source": dominant(items, "energy_source"),
                "dominant_exposure": dominant(items, "exposure_type"),
                "dominant_critical_control_failure": dominant(items, "critical_control"),
                "dominant_precursor": dominant(items, "precursor_pattern"),
                "average_sif_score": round(sum(float(item.sif_score or 0) for item in items) / len(items), 1),
                "critical_count": sum(str(item.risk_level).lower() == "critical" for item in items),
                "high_risk_count": sum(str(item.risk_level).lower() == "high" for item in items),
            }
        )
    return summaries


def _date_sort_key(value: str) -> tuple[int, str]:
    text = str(value or "").strip()
    try:
        numeric = float(text)
        if 1 <= numeric <= 100000:
            return ((date(1899, 12, 30) + timedelta(days=int(numeric))).toordinal(), text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return (datetime.strptime(text, fmt).date().toordinal(), text)
        except ValueError:
            continue
    return (0, text)


def _report_date_text(report: Any) -> str:
    observed = getattr(report, "observed_at", None)
    if isinstance(observed, datetime):
        return observed.date().isoformat()
    return str(getattr(report, "date", "") or "")


def assign_to_cluster(query_vector: np.ndarray, analyses: list[Any], embedding_model: str) -> dict | None:
    grouped: dict[int, list[np.ndarray]] = {}
    group_items: dict[int, list[Any]] = {}
    for item in analyses:
        vector = deserialize_embedding(getattr(item, "embedding", None))
        cluster_id = getattr(item, "cluster_id", None)
        if (
            getattr(item, "status", "") == "analysed"
            and cluster_id is not None
            and cluster_id >= 0
            and item.embedding_model == embedding_model
            and vector is not None
            and vector.shape == query_vector.shape
        ):
            grouped.setdefault(cluster_id, []).append(vector)
            group_items.setdefault(cluster_id, []).append(item)
    candidates = []
    for cluster_id, vectors in grouped.items():
        centroid = np.mean(np.vstack(vectors), axis=0)
        candidates.append((cosine_score(query_vector, centroid), cluster_id))
    if not candidates:
        return None
    score, cluster_id = sorted(candidates, key=lambda pair: (-pair[0], pair[1]))[0]
    if score < CLUSTER_ASSIGNMENT_MIN_SIMILARITY:
        return None
    items = group_items[cluster_id]
    return {
        "cluster_id": cluster_id,
        "cluster_code": f"C-{cluster_id + 1:02d}",
        "cluster_name": cluster_name(items),
        "assignment_similarity_percent": round(score * 100, 1),
    }
