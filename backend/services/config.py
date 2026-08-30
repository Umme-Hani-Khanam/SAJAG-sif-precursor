import os


ANALYSIS_VERSION = "sajag-analysis-v2"
HEURISTIC_EXTRACTION_MODEL = "sajag-safety-taxonomy-v1"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MINILM_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HASHING_EMBEDDING_MODEL = "sajag-hashing-384-v1"

# Explainable historical evidence weights. They must total 1.0.
SIMILARITY_WEIGHTS = {
    "semantic_similarity": 0.35,
    "hazard_match": 0.15,
    "energy_source_match": 0.10,
    "exposure_match": 0.10,
    "critical_control_match": 0.15,
    "precursor_match": 0.15,
}
SIMILAR_RESULTS_LIMIT = int(os.getenv("SIMILAR_RESULTS_LIMIT", "5"))
SIMILARITY_RESULT_MIN_SCORE = float(os.getenv("SIMILARITY_RESULT_MIN_SCORE", "0.18"))

# Cosine-distance DBSCAN parameters.
DBSCAN_EPS = float(os.getenv("DBSCAN_EPS", "0.38"))
DBSCAN_MIN_SAMPLES = int(os.getenv("DBSCAN_MIN_SAMPLES", "2"))
CLUSTER_ASSIGNMENT_MIN_SIMILARITY = float(
    os.getenv("CLUSTER_ASSIGNMENT_MIN_SIMILARITY", "0.58")
)

# Staged unclassified-pattern rules. Counts include the submitted observation.
UNCLASSIFIED_RELATED_MIN_SIMILARITY = float(
    os.getenv("UNCLASSIFIED_RELATED_MIN_SIMILARITY", "0.56")
)
PATTERN_CANDIDATE_MIN_COUNT = int(os.getenv("PATTERN_CANDIDATE_MIN_COUNT", "2"))
PATTERN_ALERT_MIN_COUNT = int(os.getenv("PATTERN_ALERT_MIN_COUNT", "4"))
PATTERN_ALERT_WINDOW_DAYS = int(os.getenv("PATTERN_ALERT_WINDOW_DAYS", "30"))

# An established cluster becomes emerging only with both frequency and acceleration.
EMERGING_CURRENT_WINDOW_DAYS = int(os.getenv("EMERGING_CURRENT_WINDOW_DAYS", "30"))
EMERGING_MIN_CURRENT_COUNT = int(os.getenv("EMERGING_MIN_CURRENT_COUNT", "4"))
EMERGING_MIN_GROWTH_RATIO = float(os.getenv("EMERGING_MIN_GROWTH_RATIO", "1.0"))
HIGH_RISK_LEVELS = {"high", "critical"}
CONTROL_ACCELERATION_MIN_CURRENT = int(os.getenv("CONTROL_ACCELERATION_MIN_CURRENT", "3"))
CONTROL_ACCELERATION_GROWTH_MULTIPLIER = float(os.getenv("CONTROL_ACCELERATION_GROWTH_MULTIPLIER", "2.0"))

assert abs(sum(SIMILARITY_WEIGHTS.values()) - 1.0) < 1e-9
