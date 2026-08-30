from conftest import add_synthetic_reports
from models import HistoricalAnalysis
from services.clustering import assign_to_cluster, summarize_clusters
from services.embeddings import build_embedding_text, encode_texts
from services.extraction import heuristic_analysis
from services.pipeline import analysis_status, batch_analyze
from services.scoring import risk_level, score_analysis


def test_batch_persists_analysis_and_functional_clusters(db_session):
    add_synthetic_reports(db_session)
    result = batch_analyze(db_session)
    rows = db_session.query(HistoricalAnalysis).all()
    assert result["analysed"] == 18
    assert result["pending"] == 0
    assert all(row.embedding and row.analysis_timestamp and row.analysis_version for row in rows)
    assert all(row.cluster_id is not None for row in rows)
    clusters = summarize_clusters(rows)
    assert len(clusters) >= 5
    assert all(cluster["report_count"] >= 2 for cluster in clusters)
    assert all(cluster["cluster_code"].startswith("C-") for cluster in clusters)


def test_new_suspended_load_assigns_to_established_cluster(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)
    rows = db_session.query(HistoricalAnalysis).all()
    text = "A worker entered the crane lifting exclusion zone beneath a suspended load."
    analysis = heuristic_analysis(text)
    model = rows[0].embedding_model
    vectors, actual_model = encode_texts([build_embedding_text(text, analysis)], force_model=model)
    cluster = assign_to_cluster(vectors[0], rows, actual_model)
    assert cluster is not None
    assert "suspended" in cluster["cluster_name"].lower()


def test_risk_scoring_is_deterministic_and_bounded():
    high = heuristic_analysis("Worker leaned beyond a scaffold guardrail without fall protection under a suspended load.")
    low = {**heuristic_analysis("General housekeeping observation"), "potential_consequence": "Minor injury", "control_status": "intact", "likelihood": "low"}
    high_score = score_analysis(high)
    low_score = score_analysis(low)
    assert high_score == score_analysis(high)
    assert high_score["total"] <= 100
    assert high_score["total"] > low_score["total"]
    assert risk_level(high_score["total"]) == "critical"
