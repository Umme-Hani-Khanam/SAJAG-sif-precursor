import json
import os
import re
from abc import ABC, abstractmethod

from fastapi import HTTPException

from services.config import GEMINI_MODEL


PHOTO_DISCLAIMER = "Image-derived findings require HSE confirmation."
PHOTO_SCHEMA_KEYS = (
    "visible_hazards", "visible_controls", "possible_missing_controls",
    "possible_exposures", "image_summary", "confidence",
)


class VisionProvider(ABC):
    @abstractmethod
    def inspect(self, content: bytes, media_type: str, description: str = "") -> dict: ...


class GeminiVisionProvider(VisionProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()

    def inspect(self, content: bytes, media_type: str, description: str = "") -> dict:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="Photo analysis is not configured. Set GEMINI_API_KEY.")
        try:
            from google import genai
            from google.genai import types

            prompt = (
                "Inspect only visible workplace-safety evidence. Return strict JSON with arrays "
                "visible_hazards, visible_controls, possible_missing_controls, possible_exposures; "
                "a concise image_summary; and confidence HIGH, MEDIUM, or LOW. Distinguish absence "
                "of visible evidence from proof that a control is absent. Do not decide final SIF risk. "
                f"Optional reporter context (not visual evidence): {description}"
            )
            response = genai.Client(api_key=self.api_key).models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, types.Part.from_bytes(data=content, mime_type=media_type)],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Configured image analysis provider failed.") from exc


def normalize_photo_findings(raw: dict) -> dict:
    result = {}
    for key in PHOTO_SCHEMA_KEYS[:4]:
        value = raw.get(key, [])
        result[key] = [re.sub(r"\s+", " ", str(item)).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
    result["image_summary"] = re.sub(r"\s+", " ", str(raw.get("image_summary", ""))).strip()
    confidence = str(raw.get("confidence", "LOW")).strip().upper()
    result["confidence"] = confidence if confidence in {"HIGH", "MEDIUM", "LOW"} else "LOW"
    if not result["image_summary"]:
        raise HTTPException(status_code=502, detail="Image provider returned no usable visual summary.")
    result["disclaimer"] = PHOTO_DISCLAIMER
    return result


def analyze_photo(content: bytes, media_type: str, description: str = "", provider: VisionProvider | None = None) -> dict:
    return normalize_photo_findings((provider or GeminiVisionProvider()).inspect(content, media_type, description))


def combined_description(description: str, findings: dict) -> tuple[str, dict]:
    observed = [
        *findings.get("visible_hazards", []), *findings.get("visible_controls", []),
        findings.get("image_summary", ""),
    ]
    inferred = [*findings.get("possible_missing_controls", []), *findings.get("possible_exposures", [])]
    parts = []
    if description.strip():
        parts.append(f"Reported by user: {description.strip()}")
    if observed:
        parts.append("Observed in image: " + "; ".join(item for item in observed if item))
    if inferred:
        parts.append("AI inferred possibilities requiring confirmation: " + "; ".join(inferred))
    return "\n".join(parts), {
        "REPORTED_BY_USER": [description.strip()] if description.strip() else [],
        "OBSERVED_IN_IMAGE": [item for item in observed if item],
        "AI_INFERRED": inferred,
    }
