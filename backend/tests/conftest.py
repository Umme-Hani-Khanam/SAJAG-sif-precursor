import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/sajag-pytest-bootstrap.db")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FORCE_HASHING_EMBEDDINGS", "true")

from database import Base, get_db  # noqa: E402
from models import HistoricalAnalysis, SafetyReport  # noqa: E402


FAMILIES = {
    "height": [
        "A scaffolder crossed an open platform edge without clipping the harness lanyard to an anchor.",
        "A technician climbed a ladder above the landing while the fall-arrest hook remained disconnected.",
        "Guardrails were missing from an elevated work deck where a worker was installing cable tray.",
    ],
    "load": [
        "A rigger stepped beneath a suspended pipe spool while the crane slewed toward the laydown area.",
        "Two helpers entered the lifting exclusion zone as a steel beam hung from the hoist.",
        "A tag-line handler stood in the line of fire below an overhead load during rigging work.",
    ],
    "electrical": [
        "An electrician opened an energized panel before the lockout and test-for-dead checks were complete.",
        "Maintenance began on a motor feeder with the LOTO lock missing from the local isolator.",
        "A live cable termination was exposed while the electrical isolation certificate remained unsigned.",
    ],
    "confined": [
        "A worker entered a storage tank before gas testing and rescue standby were confirmed.",
        "The vessel-entry team crossed the confined-space boundary without a signed entry permit.",
        "Oxygen readings were not recorded before a contractor descended into the process manhole.",
    ],
    "pressure": [
        "A fitter loosened a flange while residual pressure remained trapped in the steam line.",
        "The hydraulic hose coupling was opened before stored pressure was bled to zero.",
        "A pressurized process spool was unbolted without verifying depressurization and isolation.",
    ],
    "chemical": [
        "A chlorine connection showed a gas leak while workers nearby lacked respiratory protection.",
        "Operators approached a toxic vapour release before portable gas detection was established.",
        "A chemical transfer hose leaked and exposed the crew to inhalation and skin-contact hazards.",
    ],
}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def add_synthetic_reports(session, duplicate_description=False):
    index = 1
    for family_index, (family, descriptions) in enumerate(FAMILIES.items()):
        for description_index, description in enumerate(descriptions):
            day = 1 + family_index * 10 + description_index
            report = SafetyReport(
                report_id=f"{family[:3].upper()}-{index:03d}",
                date=f"2026-06-{min(day, 28):02d}" if family_index < 3 else f"2026-07-{min(day - 28, 28):02d}",
                location_site=f"Plant {family_index % 3 + 1}",
                department="Operations",
                activity=f"{family.title()} work",
                report_type="Near miss",
                shift="Day",
                source="Synthetic test fixture",
                company="SAJAG Test",
                region="South",
                site=f"Plant {family_index % 3 + 1}",
                description=description,
            )
            report.analysis = HistoricalAnalysis(status="pending")
            session.add(report)
            index += 1
    if duplicate_description:
        original = FAMILIES["load"][0]
        duplicate = SafetyReport(
            report_id="LOD-DUP", date="2026-07-25", location_site="Plant 2",
            department="Operations", activity="Load work", report_type="Near miss", shift="Night",
            source="Synthetic test fixture", company="SAJAG Test", region="South", site="Plant 2",
            description=original,
        )
        duplicate.analysis = HistoricalAnalysis(status="pending")
        session.add(duplicate)
    session.commit()
    return session.query(SafetyReport).all()
