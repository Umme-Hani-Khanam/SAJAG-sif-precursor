"""Evidence-based uncertainty labels; these are not calibrated probabilities."""

from services.config import HIGH_RISK_LEVELS


def assess_confidence(
    *, description: str, site: str, activity: str, analysis: dict,
    text_source: str = "user", input_quality: str | None = None,
) -> dict:
    reasons: list[str] = []
    positive = 0
    words = description.split()
    if len(words) >= 18:
        positive += 1
    else:
        reasons.append("Observation description is brief.")
    if activity.strip():
        positive += 1
    else:
        reasons.append("Observation lacks activity details.")
    if site.strip():
        positive += 1
    else:
        reasons.append("Observation site was not supplied.")
    if str(analysis.get("critical_control", "")).strip().lower() not in {"", "unknown", "not identified"}:
        positive += 1
    else:
        reasons.append("Critical control could not be identified.")
    if analysis.get("similar_reports"):
        positive += 1
    else:
        reasons.append("No close historical evidence was retrieved.")
    if (analysis.get("grounded_guidance") or {}).get("grounding_status") == "grounded":
        positive += 1
    else:
        reasons.append("No approved, temporally eligible guidance supported the analysis.")
    if text_source in {"ocr", "image"} and str(input_quality or "").upper() == "LOW":
        positive -= 1
        reasons.append(f"{text_source.upper()} input quality is low and requires confirmation.")
    label = "HIGH" if positive >= 5 else "MEDIUM" if positive >= 3 else "LOW"
    if not reasons:
        reasons.append("Description, context, extraction, and historical evidence are mutually supportive.")
    review = label == "LOW" and str(analysis.get("risk_level", "")).lower() in HIGH_RISK_LEVELS
    return {
        "label": label,
        "reasons": reasons,
        "method": "evidence_signals_v1",
        "calibrated_probability": False,
        "hse_review_recommended": review,
    }
