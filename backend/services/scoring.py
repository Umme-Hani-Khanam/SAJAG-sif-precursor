from typing import Any


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def score_potential_consequence(analysis: dict[str, str]) -> int:
    text = " ".join(
        [analysis.get("potential_consequence", ""), analysis.get("hazard", ""), analysis.get("exposure_type", "")]
    ).lower()
    if _contains(text, ("multiple fatalities", "catastrophic", "mass casualty")):
        return 30
    if _contains(text, ("fatality", "death", "permanent disability", "amputation")):
        return 26
    if _contains(text, ("serious injury", "major injury", "life-altering", "fracture", "severe burn")):
        return 20
    if _contains(text, ("recordable", "medical treatment", "lost time", "moderate injury")):
        return 12
    if _contains(text, ("minor injury", "first aid", "minor harm")):
        return 5
    return 10


def score_hazardous_energy(analysis: dict[str, str]) -> int:
    text = " ".join(
        [analysis.get("hazard", ""), analysis.get("energy_source", ""), analysis.get("exposure_type", "")]
    ).lower()
    direct = _contains(text, ("fall", "struck", "caught", "electrical", "inhalation", "explosion", "pressure", "contact", "asphyxiation"))
    major = _contains(
        text,
        ("height", "suspended load", "line of fire", "confined", "electrical", "voltage", "vehicle", "crane", "explosion", "fire", "pressure", "chemical", "toxic", "gravity"),
    )
    if major:
        return 25 if direct else 22
    if _contains(text, ("machinery", "rotating", "pinch", "sharp", "manual handling", "hot surface", "slip", "trip")):
        return 15 if direct else 12
    return 8 if text.strip() else 0


def score_control_failure(analysis: dict[str, str]) -> int:
    control = analysis.get("critical_control", "").lower()
    status = analysis.get("control_status", "").lower()
    if not f"{control} {status}".strip():
        return 0
    if _contains(status, ("missing", "bypassed", "failed", "disabled", "not used", "absent")):
        return 25
    if _contains(status, ("degraded", "ineffective", "inadequate", "partial", "damaged")):
        return 18
    if _contains(status, ("unknown", "unclear", "not verified")):
        return 10
    if _contains(status, ("intact", "available", "effective", "in place", "functional")):
        return 4
    return 12


def score_likelihood(analysis: dict[str, str]) -> int:
    likelihood = analysis.get("likelihood", "").lower()
    exposure = " ".join(
        [analysis.get("unsafe_act", ""), analysis.get("unsafe_condition", ""), analysis.get("exposure_type", "")]
    ).lower()
    if "high" in likelihood or _contains(exposure, ("directly exposed", "under suspended load", "open edge", "energized")):
        return 10
    if "medium" in likelihood or _contains(exposure, ("near miss", "adjacent exposure", "possible contact")):
        return 6
    if "low" in likelihood:
        return 2
    return 4


def score_historical_recurrence(matches: list[dict[str, Any]]) -> int:
    scores = [float(item.get("overall_match_percent", float(item.get("similarity", 0)) * 100)) for item in matches]
    recurrent = [score for score in scores if score >= 55]
    if len(recurrent) >= 4:
        return 10
    if len(recurrent) >= 2:
        return 7
    if len(recurrent) == 1:
        return 4
    return 2 if scores and max(scores) >= 45 else 0


def score_analysis(analysis: dict[str, str], matches: list[dict[str, Any]] | None = None) -> dict[str, int]:
    breakdown = {
        "potential_consequence": score_potential_consequence(analysis),
        "hazardous_energy_exposure": score_hazardous_energy(analysis),
        "critical_control_failure": score_control_failure(analysis),
        "likelihood": score_likelihood(analysis),
        "historical_recurrence": score_historical_recurrence(matches or []),
    }
    breakdown["total"] = sum(breakdown.values())
    return breakdown


def risk_level(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
