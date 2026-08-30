import hashlib
import json
import re
from typing import Iterable

import numpy as np

from services.config import HASHING_EMBEDDING_MODEL, MINILM_MODEL


_model = None
_model_unavailable = False


def build_embedding_text(description: str, analysis: dict) -> str:
    fields = [
        ("description", description),
        ("hazard", analysis.get("hazard", "")),
        ("energy", analysis.get("energy_source", "")),
        ("exposure", analysis.get("exposure_type", "")),
        ("control", analysis.get("critical_control", "")),
        ("precursor", analysis.get("precursor_pattern", "")),
    ]
    return " ".join(f"{label}: {value}" for label, value in fields if str(value).strip())


def _hashing_encode(texts: Iterable[str], dimensions: int = 384) -> np.ndarray:
    vectors = np.zeros((len(texts), dimensions), dtype=np.float32)
    for row, text in enumerate(texts):
        tokens = re.findall(r"[a-z0-9]+", str(text).lower())
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "little") % dimensions
            vectors[row, index] += 1.0
        norm = float(np.linalg.norm(vectors[row]))
        if norm:
            vectors[row] /= norm
    return vectors


def encode_texts(texts: Iterable[str], force_model: str | None = None) -> tuple[np.ndarray, str]:
    """Use MiniLM when available; retain a deterministic offline fallback for demos/tests."""

    global _model, _model_unavailable
    values = list(texts)
    if force_model == HASHING_EMBEDDING_MODEL:
        return _hashing_encode(values), HASHING_EMBEDDING_MODEL

    if not _model_unavailable:
        try:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(MINILM_MODEL)
            vectors = _model.encode(
                values,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return np.asarray(vectors, dtype=np.float32), MINILM_MODEL
        except Exception:
            _model_unavailable = True

    return _hashing_encode(values), HASHING_EMBEDDING_MODEL


def serialize_embedding(vector: np.ndarray) -> str:
    return json.dumps([round(float(value), 7) for value in vector.tolist()], separators=(",", ":"))


def deserialize_embedding(value: str | None) -> np.ndarray | None:
    if not value:
        return None
    try:
        vector = np.asarray(json.loads(value), dtype=np.float32)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return vector if vector.ndim == 1 and vector.size else None


def cosine_score(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not denominator:
        return 0.0
    return max(0.0, min(1.0, float(np.dot(left, right) / denominator)))
