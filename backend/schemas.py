from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HistoricalAnalysisResponse(BaseModel):
    report_id: str
    status: str
    error_message: str | None = None
    hazard: str | None = None
    energy_source: str | None = None
    exposure_type: str | None = None
    unsafe_act: str | None = None
    unsafe_condition: str | None = None
    critical_control: str | None = None
    control_status: str | None = None
    potential_consequence: str | None = None
    likelihood: str | None = None
    precursor_pattern: str | None = None
    life_saving_rule: str | None = None
    sif_score: float | None = None
    risk_level: str | None = None
    cluster_id: int | None = None
    analysis_timestamp: datetime | None = None
    extraction_model: str | None = None
    embedding_model: str | None = None
    analysis_version: str | None = None

    model_config = ConfigDict(from_attributes=True)


class HSEReviewResponse(BaseModel):
    review_id: str
    report_id: str
    reviewer_name: str
    reviewer_role: str
    review_status: str
    decision: str
    review_note: str | None = None
    created_at: datetime
    reviewed_risk_level: str | None = None
    reviewed_sif_score: float | None = None
    reviewed_hazard: str | None = None
    reviewed_energy_source: str | None = None
    reviewed_exposure_type: str | None = None
    reviewed_critical_control: str | None = None
    reviewed_control_status: str | None = None
    reviewed_potential_consequence: str | None = None
    reviewed_likelihood: str | None = None
    reviewed_precursor: str | None = None

    model_config = ConfigDict(from_attributes=True)


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
    observed_at: datetime | None = None
    submitted_at: datetime | None = None
    confidence_label: str | None = None
    confidence_reasons: str | None = None
    review_recommended: bool = False
    analysis: HistoricalAnalysisResponse | None = None
    reviews: list[HSEReviewResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    message: str
    demo_mode: bool = False


class UploadResponse(BaseModel):
    message: str
    total_rows: int
    inserted: int
    updated: int
    unchanged: int = 0


class AnalyzeRequest(BaseModel):
    description: str = Field(min_length=1, max_length=12000)
    site: str = ""
    activity: str = ""
    observed_at: datetime | None = None


class BatchAnalyzeRequest(BaseModel):
    include_failed: bool = True
    reanalyze_all: bool = False
    use_gemini: bool = False


class SimilarReportResponse(BaseModel):
    report_id: str
    description: str
    similarity: float
    overall_match_percent: float
    semantic_similarity: float
    hazard_match: float
    energy_source_match: float
    exposure_match: float
    critical_control_match: float
    precursor_match: float
    match_reasons: list[str]
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
    current_cluster: dict[str, Any] | None = None
    pattern_status: dict[str, Any]
    cluster_trend: dict[str, Any] | None = None
    emerging_risk: dict[str, Any] | None = None
    analysis_context: dict[str, Any]
    model_metadata: dict[str, Any]
    report_id: str | None = None
    grounded_guidance: dict[str, Any] | None = None
    historical_actions: list[dict[str, Any]] = Field(default_factory=list)
    role_recommendation: dict[str, Any] | None = None
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    observed_at: datetime | None = None
    submitted_at: datetime | None = None
    confidence: dict[str, Any] | None = None
    hse_review_recommended: bool = False
    input_provenance: dict[str, Any] | None = None
    photo_findings: dict[str, Any] | None = None
    document_extraction: dict[str, Any] | None = None


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=512)
    role: str
    site_scope: list[str] = Field(default_factory=list)
    active: bool = True


class ReviewCreate(BaseModel):
    decision: str
    review_note: str = ""
    reviewed_risk_level: str | None = None
    reviewed_sif_score: float | None = Field(default=None, ge=0, le=100)
    reviewed_hazard: str | None = None
    reviewed_energy_source: str | None = None
    reviewed_exposure_type: str | None = None
    reviewed_critical_control: str | None = None
    reviewed_control_status: str | None = None
    reviewed_potential_consequence: str | None = None
    reviewed_likelihood: str | None = None
    reviewed_precursor: str | None = None


class CAPACreate(BaseModel):
    report_id: str | None = None
    cluster_id: int | None = None
    alert_id: str | None = None
    title: str
    description: str
    action_type: str = "corrective"
    priority: str = "medium"
    owner_name: str | None = None
    owner_role: str | None = None
    due_date: datetime | None = None


class CAPAAssign(BaseModel):
    owner_name: str
    owner_role: str = "SITE_SUPERVISOR"


class CAPAStatusChange(BaseModel):
    status: str
    note: str = ""


class CAPAEvidenceCreate(BaseModel):
    evidence_type: str = "note"
    reference: str = ""
    note: str


class NoteRequest(BaseModel):
    note: str


class AlertDecisionRequest(BaseModel):
    decision: str
    reason: str = ""


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
