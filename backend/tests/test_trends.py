from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np

from services.embeddings import serialize_embedding
from services.trends import cluster_trend, emerging_cluster_patterns, staged_unclassified_pattern


def item(report_id, day, cluster_id=0, vector=None):
    return SimpleNamespace(
        report_id=report_id, status="analysed", cluster_id=cluster_id,
        embedding_model="test-model", embedding=serialize_embedding(np.asarray(vector or [1.0, 0.0])),
        precursor_pattern="Suspended-load line-of-fire exposure", critical_control="Exclusion zone",
        control_status="missing", potential_consequence="Single fatality", hazard="Suspended load",
        energy_source="Gravity", exposure_type="Struck-by", sif_score=82, risk_level="high",
        report=SimpleNamespace(report_id=report_id, date=day.isoformat(), site="Plant A", location_site="Plant A", activity="Lifting", description=f"Distinct lifting event {report_id}"),
    )


def test_trend_acceleration_and_emerging_rule():
    anchor = date(2026, 8, 30)
    rows = [item(f"OLD-{i}", anchor - timedelta(days=35 + i)) for i in range(2)]
    rows += [item(f"NEW-{i}", anchor - timedelta(days=i * 3)) for i in range(5)]
    trend = cluster_trend(rows, anchor)
    assert trend["previous_30_days"] == 2
    assert trend["last_30_days"] == 5
    assert trend["growth_percent"] == 150.0
    alerts = emerging_cluster_patterns(rows)
    assert len(alerts) == 1
    assert alerts[0]["alert_title"] == "Emerging SIF precursor pattern detected"


def test_unclassified_pattern_stages_are_evidence_based():
    anchor = date(2026, 8, 30)
    one = [item("U-1", anchor, cluster_id=-1)]
    candidate = staged_unclassified_pattern(np.asarray([1.0, 0.0]), one, "test-model")
    assert candidate["state"] == "candidate_pattern"
    many = [item(f"U-{i}", anchor - timedelta(days=i), cluster_id=-1) for i in range(3)]
    alert = staged_unclassified_pattern(np.asarray([1.0, 0.0]), many, "test-model")
    assert alert["state"] == "new_pattern_alert"
