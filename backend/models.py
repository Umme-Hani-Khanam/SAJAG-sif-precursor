from sqlalchemy import Column, Text

from database import Base


class SafetyReport(Base):
    __tablename__ = "safety_reports"

    report_id = Column(Text, primary_key=True, index=True)
    date = Column(Text, nullable=False)
    location_site = Column(Text, nullable=False)
    department = Column(Text, nullable=False)
    activity = Column(Text, nullable=False)
    report_type = Column(Text, nullable=False)
    shift = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    company = Column(Text, nullable=False)
    region = Column(Text, nullable=False)
    site = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
