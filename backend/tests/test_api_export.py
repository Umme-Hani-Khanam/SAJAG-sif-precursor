import csv
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

import main
from conftest import add_synthetic_reports
from database import get_db
from services.pipeline import batch_analyze


def test_filtered_csv_export_endpoint(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)

    def override_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_db
    main.DEFAULT_DATASET_PATH = Path("/definitely/missing.xlsx")
    try:
        client = TestClient(main.app)
        response = client.get("/reports/export.csv?risk_level=critical")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows
    assert all(row["Risk Level"] == "critical" for row in rows)
    assert {"Report ID", "Hazard", "Precursor", "Cluster ID"}.issubset(rows[0])


def test_analysis_cluster_and_analytics_endpoints(db_session):
    add_synthetic_reports(db_session)
    batch_analyze(db_session)

    def override_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(main.app)
        response = client.post(
            "/analyze",
            json={
                "description": "A rigger stood below a crane suspended load after the exclusion barrier was removed.",
                "site": "Plant 2",
                "activity": "Lifting",
            },
        )
        clusters = client.get("/clusters")
        trends = client.get("/analytics/trends?site=Plant%202")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_cluster"] is not None
    assert payload["similar_reports"][0]["match_reasons"]
    assert clusters.status_code == 200 and len(clusters.json()) >= 5
    assert trends.status_code == 200 and trends.json()["filters_applied"]["site"] == "Plant 2"
