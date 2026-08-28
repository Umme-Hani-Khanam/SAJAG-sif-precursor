from pydantic import BaseModel, ConfigDict


class SafetyReportResponse(BaseModel):
    report_id: str
    date: str
    location_site: str
    department: str
    activity: str
    report_type: str
    shift: str
    source: str
    company: str
    region: str
    site: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    message: str


class UploadResponse(BaseModel):
    message: str
    total_rows: int
    inserted: int
    updated: int


class AnalyzeRequest(BaseModel):
    description: str
    site: str = ""
    activity: str = ""


class SimilarReportResponse(BaseModel):
    report_id: str
    description: str
    similarity: float
    date: str = ""
    site: str = ""
    activity: str = ""


class ScoreBreakdownResponse(BaseModel):
    potential_consequence: int
    hazardous_energy_exposure: int
    critical_control_failure: int
    likelihood: int
    historical_recurrence: int
    total: int


class AnalyzeResponse(BaseModel):
    sif_score: float
    risk_level: str
    score_breakdown: ScoreBreakdownResponse
    hazard: str
    energy_source: str
    exposure_type: str
    unsafe_act: str
    unsafe_condition: str
    critical_control: str
    control_status: str
    potential_consequence: str
    likelihood: str
    precursor_pattern: str
    life_saving_rule: str
    similar_reports: list[SimilarReportResponse]
    site: str
    activity: str

class DatasetAnalysisResponse(BaseModel):
    total_reports: int
    high_risk: int
    medium_risk: int
    low_risk: int
    average_sif_score: float
    top_sites: list[dict]
    top_activities: list[dict]
    report_types: list[dict]
    departments: list[dict]
