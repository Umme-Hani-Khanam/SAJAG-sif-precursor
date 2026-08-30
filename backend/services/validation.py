import json
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from models import ValidationCase, ValidationDataset, ValidationRun
from services.config import ANALYSIS_VERSION, HEURISTIC_EXTRACTION_MODEL, HIGH_RISK_LEVELS
from services.extraction import extract_analysis
from services.scoring import risk_level, score_analysis


GROUND_TRUTH_COLUMNS = (
    "description", "expected_hazard", "expected_exposure", "expected_critical_control",
    "expected_precursor", "expected_risk_level",
)
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SCORING_VERSION = "sajag-validation-v1"


def normalized(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def calculate_metrics(cases: list[dict]) -> tuple[dict, dict]:
    total = len(cases)
    precursor_tp = sum(normalized(row["predicted_precursor"]) == normalized(row["expected_precursor"]) for row in cases)
    precursor_mismatches = total - precursor_tp
    precision = precursor_tp / (precursor_tp + precursor_mismatches) if total else 0.0
    recall = precursor_tp / (precursor_tp + precursor_mismatches) if total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_negatives = sum(
        normalized(row["expected_risk_level"]) in HIGH_RISK_LEVELS and
        normalized(row["predicted_risk_level"]) not in HIGH_RISK_LEVELS
        for row in cases
    )
    expected_high = sum(normalized(row["expected_risk_level"]) in HIGH_RISK_LEVELS for row in cases)
    exact = sum(normalized(row["expected_risk_level"]) == normalized(row["predicted_risk_level"]) for row in cases)
    adjacent = sum(
        abs(RISK_ORDER.get(normalized(row["expected_risk_level"]), -10) - RISK_ORDER.get(normalized(row["predicted_risk_level"]), 10)) <= 1
        for row in cases
    )
    control = sum(normalized(row["expected_critical_control"]) == normalized(row["predicted_critical_control"]) for row in cases)
    matrix = defaultdict(lambda: defaultdict(int))
    for row in cases:
        matrix[normalized(row["expected_risk_level"])][normalized(row["predicted_risk_level"])] += 1
    metrics = {
        "dataset_size": total,
        "precursor_true_positive": precursor_tp,
        "precursor_false_positive": precursor_mismatches,
        "precursor_false_negative": precursor_mismatches,
        "precursor_precision": precision, "precursor_recall": recall, "precursor_f1": f1,
        "high_critical_expected": expected_high, "high_critical_false_negatives": false_negatives,
        "high_critical_false_negative_rate": false_negatives / expected_high if expected_high else 0.0,
        "risk_exact_agreement": exact / total if total else 0.0,
        "risk_adjacent_agreement": adjacent / total if total else 0.0,
        "critical_control_agreement": control / total if total else 0.0,
    }
    return metrics, {expected: dict(predictions) for expected, predictions in matrix.items()}


def run_validation(db: Session, dataset: ValidationDataset) -> ValidationRun:
    evaluated = []
    extraction_models = set()
    for case in dataset.cases:
        extracted, model = extract_analysis(case.description, prefer_gemini=False)
        extraction_models.add(model)
        predicted_risk = risk_level(score_analysis(extracted)["total"])
        evaluated.append({
            "expected_precursor": case.expected_precursor,
            "predicted_precursor": extracted["precursor_pattern"],
            "expected_risk_level": case.expected_risk_level,
            "predicted_risk_level": predicted_risk,
            "expected_critical_control": case.expected_critical_control,
            "predicted_critical_control": extracted["critical_control"],
        })
    metrics, matrix = calculate_metrics(evaluated)
    run = ValidationRun(
        run_id=f"VAL-{uuid4().hex[:16].upper()}", dataset_id=dataset.dataset_id,
        metrics=json.dumps(metrics), confusion_matrix=json.dumps(matrix),
        model_version="+".join(sorted(extraction_models)) or HEURISTIC_EXTRACTION_MODEL,
        scoring_version=SCORING_VERSION,
    )
    db.add(run)
    db.flush()
    return run


def run_to_dict(run: ValidationRun) -> dict:
    return {
        "run_id": run.run_id, "dataset_id": run.dataset_id, "status": run.status,
        "metrics": json.loads(run.metrics), "confusion_matrix": json.loads(run.confusion_matrix),
        "model_version": run.model_version, "scoring_version": run.scoring_version,
        "validation_timestamp": run.validation_timestamp,
    }
