from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, event
from sqlalchemy.orm import relationship

from database import Base
from services.vector_types import PortableVector


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
    observed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True, default=lambda: datetime.now(timezone.utc), index=True)
    submitted_by_user_id = Column(Text, ForeignKey("users.user_id"), nullable=True, index=True)
    confidence_label = Column(Text, nullable=True, index=True)
    confidence_reasons = Column(Text, nullable=True)
    review_recommended = Column(Boolean, nullable=False, default=False, index=True)
    input_provenance = Column(Text, nullable=True)
    photo_findings = Column(Text, nullable=True)

    analysis = relationship(
        "HistoricalAnalysis",
        back_populates="report",
        cascade="all, delete-orphan",
        uselist=False,
    )
    reviews = relationship(
        "HSEReview",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="HSEReview.created_at",
    )
    capas = relationship("CAPA", back_populates="report")
    alerts = relationship("SafetyAlert", back_populates="report")


class HistoricalAnalysis(Base):
    """Persisted intelligence derived once from an immutable source report."""

    __tablename__ = "historical_analyses"

    report_id = Column(
        Text,
        ForeignKey("safety_reports.report_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    status = Column(Text, nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)

    hazard = Column(Text, nullable=True)
    energy_source = Column(Text, nullable=True)
    exposure_type = Column(Text, nullable=True)
    unsafe_act = Column(Text, nullable=True)
    unsafe_condition = Column(Text, nullable=True)
    critical_control = Column(Text, nullable=True)
    control_status = Column(Text, nullable=True)
    potential_consequence = Column(Text, nullable=True)
    likelihood = Column(Text, nullable=True)
    precursor_pattern = Column(Text, nullable=True)
    life_saving_rule = Column(Text, nullable=True)

    sif_score = Column(Float, nullable=True)
    risk_level = Column(Text, nullable=True, index=True)
    embedding = Column(Text, nullable=True)
    embedding_vector = Column(PortableVector(384), nullable=True)
    embedding_model = Column(Text, nullable=True)
    cluster_id = Column(Integer, nullable=True, index=True)

    analysis_timestamp = Column(DateTime(timezone=True), nullable=True)
    extraction_model = Column(Text, nullable=True)
    analysis_version = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    report = relationship("SafetyReport", back_populates="analysis")


class HSEReview(Base):
    __tablename__ = "hse_reviews"

    review_id = Column(Text, primary_key=True)
    report_id = Column(Text, ForeignKey("safety_reports.report_id"), nullable=False, index=True)
    reviewer_name = Column(Text, nullable=False)
    reviewer_role = Column(Text, nullable=False)
    review_status = Column(Text, nullable=False, index=True)
    decision = Column(Text, nullable=False)

    ai_risk_level = Column(Text, nullable=True)
    reviewed_risk_level = Column(Text, nullable=True)
    ai_sif_score = Column(Float, nullable=True)
    reviewed_sif_score = Column(Float, nullable=True)
    ai_hazard = Column(Text, nullable=True)
    reviewed_hazard = Column(Text, nullable=True)
    ai_energy_source = Column(Text, nullable=True)
    reviewed_energy_source = Column(Text, nullable=True)
    ai_exposure_type = Column(Text, nullable=True)
    reviewed_exposure_type = Column(Text, nullable=True)
    ai_critical_control = Column(Text, nullable=True)
    reviewed_critical_control = Column(Text, nullable=True)
    ai_control_status = Column(Text, nullable=True)
    reviewed_control_status = Column(Text, nullable=True)
    ai_potential_consequence = Column(Text, nullable=True)
    reviewed_potential_consequence = Column(Text, nullable=True)
    ai_likelihood = Column(Text, nullable=True)
    reviewed_likelihood = Column(Text, nullable=True)
    ai_precursor = Column(Text, nullable=True)
    reviewed_precursor = Column(Text, nullable=True)

    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    report = relationship("SafetyReport", back_populates="reviews")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id = Column(Text, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    actor_name = Column(Text, nullable=False, index=True)
    actor_role = Column(Text, nullable=False, index=True)
    event_type = Column(Text, nullable=False, index=True)
    entity_type = Column(Text, nullable=False, index=True)
    entity_id = Column(Text, nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)


@event.listens_for(AuditEvent, "before_update")
def _prevent_audit_update(*_):
    raise ValueError("Audit events are append-only and cannot be updated.")


@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_delete(*_):
    raise ValueError("Audit events are append-only and cannot be deleted.")


class CAPA(Base):
    __tablename__ = "capas"

    capa_id = Column(Text, primary_key=True)
    report_id = Column(Text, ForeignKey("safety_reports.report_id"), nullable=True, index=True)
    cluster_id = Column(Integer, nullable=True, index=True)
    alert_id = Column(Text, ForeignKey("safety_alerts.alert_id"), nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    action_type = Column(Text, nullable=False)
    priority = Column(Text, nullable=False, index=True)
    owner_name = Column(Text, nullable=True, index=True)
    owner_role = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_by_role = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(Text, nullable=False, default="open", index=True)
    completion_note = Column(Text, nullable=True)
    verification_note = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Text, nullable=True)

    report = relationship("SafetyReport", back_populates="capas")
    evidence = relationship("CAPAEvidence", back_populates="capa", cascade="all, delete-orphan")
    alert = relationship("SafetyAlert", back_populates="capa", foreign_keys=[alert_id])


class CAPAEvidence(Base):
    __tablename__ = "capa_evidence"

    evidence_id = Column(Text, primary_key=True)
    capa_id = Column(Text, ForeignKey("capas.capa_id"), nullable=False, index=True)
    evidence_type = Column(Text, nullable=False, default="note")
    reference = Column(Text, nullable=True)
    note = Column(Text, nullable=False)
    added_by = Column(Text, nullable=False)
    added_by_role = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    attachment_id = Column(Text, ForeignKey("attachments.attachment_id"), nullable=True)
    capa = relationship("CAPA", back_populates="evidence")


class SafetyDocument(Base):
    __tablename__ = "safety_documents"

    document_id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    organization = Column(Text, nullable=False)
    version = Column(Text, nullable=True)
    effective_date = Column(Text, nullable=True)
    source_reference = Column(Text, nullable=True)
    filename = Column(Text, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    uploaded_by = Column(Text, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0)
    status = Column(Text, nullable=False, default="DRAFT", index=True)
    review_date = Column(Text, nullable=True, index=True)
    approved_by = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    supersedes_document_id = Column(Text, ForeignKey("safety_documents.document_id"), nullable=True)
    attachment_id = Column(Text, ForeignKey("attachments.attachment_id"), nullable=True)
    indexing_status = Column(Text, nullable=False, default="pending", index=True)
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id = Column(Text, primary_key=True)
    document_id = Column(Text, ForeignKey("safety_documents.document_id"), nullable=False, index=True)
    section = Column(Text, nullable=True)
    page = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False)
    embedding_model = Column(Text, nullable=False)
    # SQLite stores the portable JSON representation. The PostgreSQL migration
    # creates this as pgvector's vector type for indexed nearest-neighbour search.
    embedding_vector = Column(PortableVector(384), nullable=True)
    document = relationship("SafetyDocument", back_populates="chunks")


class SafetyAlert(Base):
    __tablename__ = "safety_alerts"

    alert_id = Column(Text, primary_key=True)
    report_id = Column(Text, ForeignKey("safety_reports.report_id"), nullable=True, index=True)
    cluster_id = Column(Integer, nullable=True, index=True)
    alert_type = Column(Text, nullable=False, index=True)
    severity = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="open", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(Text, nullable=True)
    decision_reason = Column(Text, nullable=True)
    report = relationship("SafetyReport", back_populates="alerts")
    capa = relationship("CAPA", back_populates="alert", uselist=False, foreign_keys="CAPA.alert_id")


class User(Base):
    __tablename__ = "users"

    user_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True, index=True)
    username = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, index=True)
    site_scope = Column(Text, nullable=False, default="[]")
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    session_id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User")


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    job_id = Column(Text, primary_key=True)
    job_type = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default="queued", index=True)
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=0)
    payload = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_by_user_id = Column(Text, ForeignKey("users.user_id"), nullable=True, index=True)
    created_by_name = Column(Text, nullable=False)
    site = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Text, primary_key=True)
    recipient_user_id = Column(Text, ForeignKey("users.user_id"), nullable=True, index=True)
    recipient_role = Column(Text, nullable=True, index=True)
    recipient_site = Column(Text, nullable=True, index=True)
    notification_type = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=True)
    entity_id = Column(Text, nullable=True, index=True)
    dedupe_key = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True, index=True)


class NotificationRead(Base):
    """Per-recipient read receipt for role/site-targeted notifications."""

    __tablename__ = "notification_reads"
    __table_args__ = (UniqueConstraint("notification_id", "reader_key", name="uq_notification_reader"),)

    receipt_id = Column(Text, primary_key=True)
    notification_id = Column(Text, ForeignKey("notifications.notification_id", ondelete="CASCADE"), nullable=False, index=True)
    reader_key = Column(Text, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id = Column(Text, primary_key=True)
    entity_type = Column(Text, nullable=False, index=True)
    entity_id = Column(Text, nullable=False, index=True)
    filename = Column(Text, nullable=False)
    storage_key = Column(Text, nullable=False, unique=True)
    media_type = Column(Text, nullable=False)
    size = Column(Integer, nullable=False)
    uploaded_by = Column(Text, nullable=False)
    uploaded_by_user_id = Column(Text, ForeignKey("users.user_id"), nullable=True, index=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    description = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=False)


class PhotoAnalysis(Base):
    __tablename__ = "photo_analyses"

    photo_analysis_id = Column(Text, primary_key=True)
    report_id = Column(Text, ForeignKey("safety_reports.report_id"), nullable=True, index=True)
    attachment_id = Column(Text, ForeignKey("attachments.attachment_id"), nullable=False)
    visible_hazards = Column(Text, nullable=False, default="[]")
    visible_controls = Column(Text, nullable=False, default="[]")
    possible_missing_controls = Column(Text, nullable=False, default="[]")
    possible_exposures = Column(Text, nullable=False, default="[]")
    image_summary = Column(Text, nullable=False)
    confidence = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ValidationDataset(Base):
    __tablename__ = "validation_datasets"

    dataset_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    case_count = Column(Integer, nullable=False, default=0)
    cases = relationship("ValidationCase", back_populates="dataset", cascade="all, delete-orphan")


class ValidationCase(Base):
    __tablename__ = "validation_cases"

    case_id = Column(Text, primary_key=True)
    dataset_id = Column(Text, ForeignKey("validation_datasets.dataset_id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    site = Column(Text, nullable=True)
    activity = Column(Text, nullable=True)
    expected_hazard = Column(Text, nullable=False)
    expected_exposure = Column(Text, nullable=False)
    expected_critical_control = Column(Text, nullable=False)
    expected_precursor = Column(Text, nullable=False)
    expected_risk_level = Column(Text, nullable=False)
    dataset = relationship("ValidationDataset", back_populates="cases")


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    run_id = Column(Text, primary_key=True)
    dataset_id = Column(Text, ForeignKey("validation_datasets.dataset_id"), nullable=False, index=True)
    status = Column(Text, nullable=False, default="completed", index=True)
    metrics = Column(Text, nullable=False)
    confusion_matrix = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    scoring_version = Column(Text, nullable=False)
    validation_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "notification_type", name="uq_notification_preference"),)

    preference_id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
