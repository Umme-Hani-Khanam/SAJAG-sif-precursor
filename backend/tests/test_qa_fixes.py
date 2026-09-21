import csv
from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest
from fastapi.testclient import TestClient

import main
from database import get_db
from models import HistoricalAnalysis, SafetyReport, ValidationCase
from services.clustering import UNCLASSIFIED_CLUSTER_LABEL, cluster_display_label
from services.extraction import heuristic_analysis
from services.scoring import risk_level, score_analysis


MANAGER_HEADERS = {"X-Actor-Name": "QA Manager", "X-Actor-Role": "HSE_MANAGER"}


def client_for(db_session):
    def override_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_db
    return TestClient(main.app)


def analysed_report(
    report_id: str,
    legacy_date: str,
    *,
    cluster_id: int = 0,
    observed_at: datetime | None = None,
) -> SafetyReport:
    report = SafetyReport(
        report_id=report_id,
        date=legacy_date,
        location_site="QA Site",
        department="Operations",
        activity="QA activity",
        report_type="Observation",
        shift="Day",
        source="QA",
        company="SAJAG",
        region="South",
        site="QA Site",
        description=f"QA report {report_id}",
        observed_at=observed_at,
    )
    report.analysis = HistoricalAnalysis(
        status="analysed",
        hazard="QA hazard",
        energy_source="QA energy",
        exposure_type="QA exposure",
        critical_control="QA control",
        control_status="degraded",
        potential_consequence="Minor injury",
        likelihood="low",
        precursor_pattern="QA precursor",
        sif_score=37,
        risk_level="low",
        cluster_id=cluster_id,
    )
    return report


def upload_validation(client: TestClient, headers: str, row: str, name: str = "QA labels"):
    payload = f"{headers}\n{row}\n".encode("utf-8")
    return client.post(
        "/validation/datasets",
        headers=MANAGER_HEADERS,
        data={"name": name},
        files={"file": ("labels.csv", payload, "text/csv")},
    )


def test_cluster_display_mapping_is_consistent_across_filters_details_trends_and_export(db_session):
    reports = [analysed_report(f"CL-{cluster_id}", f"2026-06-{10 + cluster_id:02d}", cluster_id=cluster_id) for cluster_id in range(3)]
    reports.append(analysed_report("CL-NOISE", "2026-06-20", cluster_id=-1))
    db_session.add_all(reports)
    db_session.commit()
    client = client_for(db_session)
    try:
        clusters = client.get("/clusters", headers=MANAGER_HEADERS).json()
        assert [(item["cluster_id"], item["cluster_code"]) for item in clusters] == [
            (cluster_id, cluster_display_label(cluster_id)) for cluster_id in range(3)
        ]
        assert all(item["cluster_id"] >= 0 for item in clusters)

        for cluster_id in range(3):
            displayed = cluster_display_label(cluster_id)
            rows = client.get(f"/reports?cluster_id={cluster_id}", headers=MANAGER_HEADERS).json()
            assert [row["report_id"] for row in rows] == [f"CL-{cluster_id}"]
            assert rows[0]["analysis"]["cluster_id"] == cluster_id
            assert rows[0]["analysis"]["cluster_code"] == displayed

            detail = client.get(f"/clusters/{cluster_id}", headers=MANAGER_HEADERS).json()
            assert detail["cluster_code"] == displayed
            assert [row["report_id"] for row in detail["reports"]] == [f"CL-{cluster_id}"]

            trends = client.get(f"/analytics/trends?cluster_id={cluster_id}", headers=MANAGER_HEADERS).json()
            assert trends["filters_applied"]["cluster_id"] == cluster_id
            assert sum(point["reports"] for point in trends["series"]) == 1

            exported = client.get(f"/reports/export.csv?cluster_id={cluster_id}", headers=MANAGER_HEADERS)
            export_rows = list(csv.DictReader(StringIO(exported.text)))
            assert [(row["Report ID"], row["Cluster ID"], row["Cluster"]) for row in export_rows] == [
                (f"CL-{cluster_id}", str(cluster_id), displayed)
            ]

        noise = client.get("/reports?cluster_id=-1", headers=MANAGER_HEADERS).json()
        assert [row["report_id"] for row in noise] == ["CL-NOISE"]
        assert noise[0]["analysis"]["cluster_code"] == UNCLASSIFIED_CLUSTER_LABEL
        assert client.get("/clusters/-1", headers=MANAGER_HEADERS).status_code == 404
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("headers", "expected_control"),
    [
        (
            "description,expected_hazard,expected_exposure,expected_critical_control,expected_precursor,expected_risk_level",
            "Canonical control",
        ),
        (
            "description,expected_hazard,expected_exposure,expected_control,expected_precursor,expected_risk_level",
            "Legacy control",
        ),
        (
            "\ufeffdescription,expected_hazard,expected_exposure,expected_critical_control,expected_precursor,expected_risk_level",
            "BOM control",
        ),
        (
            " Description , EXPECTED_HAZARD , expected_exposure , Expected_Critical_Control , expected_precursor , EXPECTED_RISK_LEVEL ",
            "Normalized control",
        ),
    ],
)
def test_validation_csv_accepts_canonical_alias_bom_and_normalized_headers(db_session, headers, expected_control):
    client = client_for(db_session)
    try:
        response = upload_validation(
            client,
            headers,
            f"QA observation,QA hazard,QA exposure,{expected_control},QA precursor,low",
            name=f"{expected_control} labels",
        )
        assert response.status_code == 200, response.text
        case = db_session.query(ValidationCase).filter_by(dataset_id=response.json()["dataset_id"]).one()
        assert case.expected_critical_control == expected_control
    finally:
        main.app.dependency_overrides.clear()


def test_validation_alias_upload_persists_and_runs_metrics(db_session):
    client = client_for(db_session)
    try:
        response = upload_validation(
            client,
            "description,expected_hazard,expected_exposure,expected_control,expected_precursor,expected_risk_level",
            "Worker below suspended load,Suspended load,Line of fire,Exclusion zone,Suspended-load line-of-fire exposure,critical",
        )
        assert response.status_code == 200, response.text
        dataset_id = response.json()["dataset_id"]
        case = db_session.query(ValidationCase).filter_by(dataset_id=dataset_id).one()
        assert case.expected_critical_control == "Exclusion zone"

        run = client.post(f"/validation/datasets/{dataset_id}/run", headers=MANAGER_HEADERS)
        assert run.status_code == 200, run.text
        assert run.json()["metrics"]["dataset_size"] == 1
        assert "precursor_f1" in run.json()["metrics"]
    finally:
        main.app.dependency_overrides.clear()


def test_validation_csv_missing_control_columns_returns_complete_contract_error(db_session):
    client = client_for(db_session)
    try:
        response = upload_validation(
            client,
            "description,expected_hazard,expected_exposure,expected_precursor,expected_risk_level",
            "QA observation,QA hazard,QA exposure,QA precursor,low",
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["missing_columns"] == ["expected_critical_control"]
        assert detail["accepted_aliases"] == {"expected_control": "expected_critical_control"}
        assert detail["received_columns"]
        assert "expected_critical_control" in detail["required_columns"]
    finally:
        main.app.dependency_overrides.clear()


def test_validation_csv_rejects_conflicting_canonical_and_alias_values(db_session):
    client = client_for(db_session)
    try:
        response = upload_validation(
            client,
            "description,expected_hazard,expected_exposure,expected_critical_control,expected_control,expected_precursor,expected_risk_level",
            "QA observation,QA hazard,QA exposure,Canonical control,Different legacy control,QA precursor,low",
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "conflicting" in detail["message"].lower()
        assert detail["conflict_rows"] == [2]
        assert detail["missing_columns"] == []
    finally:
        main.app.dependency_overrides.clear()


def test_effective_event_date_filters_are_inclusive_and_match_reports_export_and_trends(db_session):
    ist = timezone(timedelta(hours=5, minutes=30))
    db_session.add_all([
        analysed_report("DATE-10", "1999-01-01", observed_at=datetime(2026, 6, 10, 23, 30, tzinfo=timezone.utc)),
        analysed_report("DATE-11", "2026-06-11"),
        analysed_report("DATE-15", "2000-01-01", observed_at=datetime(2026, 6, 15, 1, 0, tzinfo=ist)),
        analysed_report("DATE-16", "16/06/2026"),
        analysed_report("DATE-BAD", "not-a-date"),
    ])
    db_session.commit()
    client = client_for(db_session)
    try:
        exact_query = "date_from=2026-06-10&date_to=2026-06-10"
        exact = client.get(f"/reports?{exact_query}", headers=MANAGER_HEADERS).json()
        assert [(row["report_id"], row["effective_event_date"]) for row in exact] == [("DATE-10", "2026-06-10")]

        range_query = "date_from=2026-06-10&date_to=2026-06-15"
        ranged = client.get(f"/reports?{range_query}", headers=MANAGER_HEADERS).json()
        assert {row["report_id"] for row in ranged} == {"DATE-10", "DATE-11", "DATE-15"}

        from_only = client.get("/reports?date_from=2026-06-15", headers=MANAGER_HEADERS).json()
        assert {row["report_id"] for row in from_only} == {"DATE-15", "DATE-16"}
        to_only = client.get("/reports?date_to=2026-06-11", headers=MANAGER_HEADERS).json()
        assert {row["report_id"] for row in to_only} == {"DATE-10", "DATE-11"}

        exported = client.get(f"/reports/export.csv?{range_query}", headers=MANAGER_HEADERS)
        export_rows = list(csv.DictReader(StringIO(exported.text)))
        assert {row["Report ID"] for row in export_rows} == {row["report_id"] for row in ranged}
        assert {row["Effective Event Date"] for row in export_rows} == {"2026-06-10", "2026-06-11", "2026-06-15"}

        trends = client.get(f"/analytics/trends?{range_query}", headers=MANAGER_HEADERS).json()
        assert sum(point["reports"] for point in trends["series"]) == len(ranged) == 3
        assert trends["filters_applied"]["date_from"] == "2026-06-10"
        assert trends["filters_applied"]["date_to"] == "2026-06-15"
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "description",
    [
        "A cardboard box was left in a walkway with no hazardous energy, height exposure, vehicle interaction, or critical-control failure.",
        "A minor water spill was found near an office sink with no high-energy exposure, chemical release, or serious injury potential.",
    ],
)
def test_explicit_low_energy_housekeeping_remains_low_risk(description):
    extracted = heuristic_analysis(description)
    breakdown = score_analysis(extracted)
    assert extracted["potential_consequence"] == "Minor injury"
    assert extracted["likelihood"] == "low"
    assert extracted["control_status"] == "degraded"
    assert extracted["energy_source"].startswith("Low-energy")
    assert breakdown == {
        "potential_consequence": 5,
        "hazardous_energy_exposure": 12,
        "critical_control_failure": 18,
        "likelihood": 2,
        "historical_recurrence": 0,
        "total": 37,
    }
    assert risk_level(breakdown["total"]) == "low"


@pytest.mark.parametrize(
    "description",
    [
        "A worker was exposed at an unprotected edge while working at height after the fall-arrest system was not connected.",
        "A suspended load passed over workers after the exclusion-zone control failed.",
        "Maintenance began on energized equipment without lockout/tagout isolation.",
        "Workers entered an area after toxic gas controls were lost and the gas detector alarmed.",
    ],
)
def test_genuine_high_energy_control_failures_remain_high_or_critical(description):
    extracted = heuristic_analysis(description)
    breakdown = score_analysis(extracted)
    assert extracted["control_status"] == "missing"
    assert breakdown["hazardous_energy_exposure"] == 25
    assert risk_level(breakdown["total"]) in {"high", "critical"}


def test_risk_thresholds_remain_unchanged():
    assert risk_level(39) == "low"
    assert risk_level(40) == "medium"
    assert risk_level(69) == "medium"
    assert risk_level(70) == "high"
    assert risk_level(84) == "high"
    assert risk_level(85) == "critical"
