import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from services.config import GEMINI_MODEL, HEURISTIC_EXTRACTION_MODEL


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_FILE)

ANALYSIS_FIELDS = (
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
_gemini_client = None


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def heuristic_analysis(description: str) -> dict[str, str]:
    """Deterministic safety taxonomy used for repeatable batch processing and fallback."""

    text = re.sub(r"\s+", " ", str(description or "")).strip().lower()
    height = _contains(text, "height", "scaffold", "guardrail", "harness", "fall protection", "open edge", "ladder")
    load = _contains(text, "suspended load", "overhead load", "lifting", "crane", "rigging", "hoist")
    electrical = _contains(text, "electrical", "energized", "voltage", "arc flash", "panel", "loto", "lockout")
    confined = _contains(text, "confined space", "vessel entry", "tank entry", "manhole", "oxygen deficient")
    pressure = _contains(text, "pressure", "pressurized", "stored energy", "steam release", "hydraulic release")
    chemical = _contains(text, "chemical", "toxic", "gas", "vapour", "vapor", "leak", "h2s", "chlorine")
    vehicle = _contains(text, "vehicle", "reversing", "forklift", "traffic", "mobile equipment")
    machinery = _contains(text, "rotating", "machine", "pinch point", "unguarded")
    hot_work = _contains(text, "hot work", "welding", "spark", "flammable")

    missing = _contains(text, "without", "missing", "lacked", "no ", "not wearing", "bypassed", "failed")
    degraded = _contains(text, "inadequate", "improper", "damaged", "potential leak", "not fully")
    status = "missing" if missing else "degraded" if degraded else "unknown"

    if height and load:
        values = {
            "hazard": "Work at height and suspended load",
            "energy_source": "Gravity and suspended-load mechanical energy",
            "exposure_type": "Fall and struck-by / line of fire",
            "critical_control": "Fall protection and suspended-load exclusion zone",
            "potential_consequence": "Single fatality",
            "likelihood": "high",
            "precursor_pattern": "Work at height with suspended-load line-of-fire exposure",
            "life_saving_rule": "Protect against falls and stay out of the line of fire",
        }
    elif height:
        values = {
            "hazard": "Work at height",
            "energy_source": "Gravity",
            "exposure_type": "Fall from height",
            "critical_control": "Certified fall protection and guarded work platform",
            "potential_consequence": "Single fatality",
            "likelihood": "high" if missing else "medium",
            "precursor_pattern": "Unprotected work at height",
            "life_saving_rule": "Protect yourself against a fall when working at height",
        }
    elif load:
        values = {
            "hazard": "Suspended load",
            "energy_source": "Gravity and mechanical lifting energy",
            "exposure_type": "Struck-by / line of fire",
            "critical_control": "Barricaded lifting exclusion zone",
            "potential_consequence": "Single fatality",
            "likelihood": "high" if missing else "medium",
            "precursor_pattern": "Suspended-load line-of-fire exposure",
            "life_saving_rule": "Keep yourself and others out of the line of fire",
        }
    elif electrical:
        values = {
            "hazard": "Electrical energy",
            "energy_source": "Electricity",
            "exposure_type": "Electrical contact / arc flash",
            "critical_control": "Isolation, lockout and test for dead",
            "potential_consequence": "Single fatality",
            "likelihood": "high" if _contains(text, "energized", "live", "bypassed") else "medium",
            "precursor_pattern": "Electrical isolation / LOTO failure",
            "life_saving_rule": "Verify isolation and zero energy before work begins",
        }
    elif confined:
        values = {
            "hazard": "Confined space atmosphere",
            "energy_source": "Oxygen deficiency or hazardous atmosphere",
            "exposure_type": "Asphyxiation / toxic inhalation",
            "critical_control": "Entry permit, gas testing and rescue readiness",
            "potential_consequence": "Multiple fatalities",
            "likelihood": "high" if missing else "medium",
            "precursor_pattern": "Confined-space entry control failure",
            "life_saving_rule": "Obtain authorization before entering a confined space",
        }
    elif pressure:
        values = {
            "hazard": "Uncontrolled pressure release",
            "energy_source": "Stored pressure",
            "exposure_type": "Pressure release / struck-by",
            "critical_control": "Depressurization, isolation and zero-energy verification",
            "potential_consequence": "Single fatality",
            "likelihood": "high" if missing else "medium",
            "precursor_pattern": "Stored-pressure isolation failure",
            "life_saving_rule": "Verify isolation and zero energy before work begins",
        }
    elif chemical:
        values = {
            "hazard": "Hazardous chemical or toxic gas",
            "energy_source": "Chemical toxicity",
            "exposure_type": "Chemical inhalation / contact",
            "critical_control": "Leak isolation, gas detection and respiratory protection",
            "potential_consequence": "Single fatality",
            "likelihood": "high" if _contains(text, "toxic", "h2s", "chlorine", "gas leak") else "medium",
            "precursor_pattern": "Loss of containment / toxic exposure",
            "life_saving_rule": "Control hazardous substances and verify the atmosphere",
        }
    elif vehicle:
        values = {
            "hazard": "Mobile equipment interaction",
            "energy_source": "Vehicle kinetic energy",
            "exposure_type": "Vehicle struck-by",
            "critical_control": "Pedestrian segregation and reversing controls",
            "potential_consequence": "Single fatality",
            "likelihood": "medium",
            "precursor_pattern": "Vehicle-pedestrian line-of-fire exposure",
            "life_saving_rule": "Keep yourself and others out of the line of fire",
        }
    elif machinery:
        values = {
            "hazard": "Moving machinery",
            "energy_source": "Mechanical energy",
            "exposure_type": "Caught-in / entanglement",
            "critical_control": "Machine guarding and safe exclusion distance",
            "potential_consequence": "Permanent disability",
            "likelihood": "medium",
            "precursor_pattern": "Exposure to unguarded moving equipment",
            "life_saving_rule": "Verify isolation before working on moving equipment",
        }
    elif hot_work:
        values = {
            "hazard": "Fire and explosion",
            "energy_source": "Heat and ignition energy",
            "exposure_type": "Fire / explosion",
            "critical_control": "Hot-work permit, gas test and fire watch",
            "potential_consequence": "Multiple fatalities",
            "likelihood": "medium",
            "precursor_pattern": "Hot-work ignition-control failure",
            "life_saving_rule": "Control flammables and ignition sources",
        }
    else:
        values = {
            "hazard": "General workplace hazard",
            "energy_source": "Unspecified hazardous energy",
            "exposure_type": "Potential worker exposure",
            "critical_control": "Task risk assessment and verified controls",
            "potential_consequence": "Serious injury",
            "likelihood": "medium",
            "precursor_pattern": "Unrecognized precursor candidate",
            "life_saving_rule": "Stop work and verify critical controls",
        }

    values.update(
        {
            "unsafe_act": _unsafe_act(text, values["precursor_pattern"]),
            "unsafe_condition": _unsafe_condition(text, values["hazard"]),
            "control_status": status,
        }
    )
    return {field: str(values.get(field, "")).strip() for field in ANALYSIS_FIELDS}


def _unsafe_act(text: str, precursor: str) -> str:
    if _contains(text, "without", "bypassed", "not wearing", "leaned beyond", "approaching"):
        return f"Work proceeded without fully applying controls for {precursor.lower()}"
    return "Unsafe exposure was allowed to develop during the task"


def _unsafe_condition(text: str, hazard: str) -> str:
    if _contains(text, "inadequate", "missing", "lacked", "without", "potential leak"):
        return f"Required controls were absent or inadequate around {hazard.lower()}"
    return f"Worker exposure to {hazard.lower()} was not fully controlled"


def _gemini_key() -> str:
    value = os.getenv("GEMINI_API_KEY") or dotenv_values(ENV_FILE).get("GEMINI_API_KEY", "")
    return str(value or "").strip()


def gemini_analysis(description: str) -> dict[str, str]:
    global _gemini_client
    key = _gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    from google import genai
    from google.genai import types

    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=key)
    prompt = f"""Analyze this workplace safety observation as a SIF-precursor specialist.
Return concise JSON only. Do not calculate a numeric score.
Description: {description}
Likelihood must be low, medium, or high. Control status should be intact, degraded,
missing, bypassed, failed, or unknown. Fields: {', '.join(ANALYSIS_FIELDS)}."""
    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {field: {"type": "string"} for field in ANALYSIS_FIELDS},
                "required": list(ANALYSIS_FIELDS),
            },
        ),
    )
    parsed = json.loads(response.text or "{}")
    return {field: str(parsed.get(field, "")).strip() for field in ANALYSIS_FIELDS}


def extract_analysis(description: str, prefer_gemini: bool = True) -> tuple[dict[str, str], str]:
    if prefer_gemini and _gemini_key():
        try:
            return gemini_analysis(description), GEMINI_MODEL
        except Exception:
            # The deterministic fallback keeps the safety workflow available during quota/network failure.
            pass
    return heuristic_analysis(description), HEURISTIC_EXTRACTION_MODEL
