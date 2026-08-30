from conftest import FAMILIES, add_synthetic_reports
from models import HistoricalAnalysis, SafetyReport
from services.embeddings import build_embedding_text, encode_texts
from services.extraction import heuristic_analysis
from services.pipeline import batch_analyze
from services.similarity import rank_similar_reports


def test_similar_incidents_rank_above_unrelated_and_are_deterministic(db_session):
    add_synthetic_reports(db_session, duplicate_description=True)
    batch_analyze(db_session)
    query = "A helper walked below a crane suspended load after the lifting exclusion zone barrier was removed."
    analysis = heuristic_analysis(query)
    histories = db_session.query(HistoricalAnalysis).all()
    model = histories[0].embedding_model
    vectors, actual_model = encode_texts([build_embedding_text(query, analysis)], force_model=model)
    first = rank_similar_reports(analysis, vectors[0], histories, embedding_model=actual_model, minimum_score=0)
    second = rank_similar_reports(analysis, vectors[0], histories, embedding_model=actual_model, minimum_score=0)

    assert first == second
    assert "suspended" in first[0]["description"].lower() or "lifting" in first[0]["description"].lower()
    assert first[0]["overall_match_percent"] >= 75
    assert first[0]["overall_match_percent"] > first[-1]["overall_match_percent"]
    assert first[-1]["overall_match_percent"] < 70
    assert len({row["report_id"] for row in first}) == len(first)
    assert len({" ".join(row["description"].lower().split()) for row in first}) == len(first)
    assert len({row["overall_match_percent"] for row in first}) > 1
    assert all(row["match_reasons"] for row in first)


def test_source_duplicate_root_cause_is_content_not_report_id(db_session):
    add_synthetic_reports(db_session, duplicate_description=True)
    reports = db_session.query(SafetyReport).all()
    duplicate_text = FAMILIES["load"][0]
    duplicate_rows = [row for row in reports if row.description == duplicate_text]
    assert len(duplicate_rows) == 2
    assert len({row.report_id for row in duplicate_rows}) == 2
    batch_analyze(db_session)
    db_session.refresh(duplicate_rows[0])
    db_session.refresh(duplicate_rows[1])
    assert duplicate_rows[0].analysis.embedding == duplicate_rows[1].analysis.embedding
