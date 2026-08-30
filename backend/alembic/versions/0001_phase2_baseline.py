"""Phase 1 and Phase 2 baseline schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase2_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("safety_reports",
        sa.Column("report_id", sa.Text(), primary_key=True), sa.Column("date", sa.Text(), nullable=False),
        sa.Column("location_site", sa.Text(), nullable=False), sa.Column("department", sa.Text(), nullable=False),
        sa.Column("activity", sa.Text(), nullable=False), sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("shift", sa.Text(), nullable=False), sa.Column("source", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False), sa.Column("region", sa.Text(), nullable=False),
        sa.Column("site", sa.Text(), nullable=False), sa.Column("description", sa.Text(), nullable=False))
    op.create_table("historical_analyses",
        sa.Column("report_id", sa.Text(), sa.ForeignKey("safety_reports.report_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False), sa.Column("error_message", sa.Text()),
        *[sa.Column(name, sa.Text()) for name in ("hazard", "energy_source", "exposure_type", "unsafe_act", "unsafe_condition", "critical_control", "control_status", "potential_consequence", "likelihood", "precursor_pattern", "life_saving_rule")],
        sa.Column("sif_score", sa.Float()), sa.Column("risk_level", sa.Text()), sa.Column("embedding", sa.Text()),
        sa.Column("embedding_model", sa.Text()), sa.Column("cluster_id", sa.Integer()),
        sa.Column("analysis_timestamp", sa.DateTime(timezone=True)), sa.Column("extraction_model", sa.Text()),
        sa.Column("analysis_version", sa.Text()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("hse_reviews", sa.Column("review_id", sa.Text(), primary_key=True), sa.Column("report_id", sa.Text(), sa.ForeignKey("safety_reports.report_id"), nullable=False),
        sa.Column("reviewer_name", sa.Text(), nullable=False), sa.Column("reviewer_role", sa.Text(), nullable=False), sa.Column("review_status", sa.Text(), nullable=False), sa.Column("decision", sa.Text(), nullable=False),
        *[sa.Column(name, sa.Text()) for name in ("ai_risk_level", "reviewed_risk_level", "ai_hazard", "reviewed_hazard", "ai_energy_source", "reviewed_energy_source", "ai_exposure_type", "reviewed_exposure_type", "ai_critical_control", "reviewed_critical_control", "ai_control_status", "reviewed_control_status", "ai_potential_consequence", "reviewed_potential_consequence", "ai_likelihood", "reviewed_likelihood", "ai_precursor", "reviewed_precursor", "review_note")],
        sa.Column("ai_sif_score", sa.Float()), sa.Column("reviewed_sif_score", sa.Float()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events", sa.Column("event_id", sa.Text(), primary_key=True), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("actor_name", sa.Text(), nullable=False), sa.Column("actor_role", sa.Text(), nullable=False), sa.Column("event_type", sa.Text(), nullable=False), sa.Column("entity_type", sa.Text(), nullable=False), sa.Column("entity_id", sa.Text(), nullable=False), sa.Column("old_value", sa.Text()), sa.Column("new_value", sa.Text()), sa.Column("reason", sa.Text()))
    op.create_table("safety_documents", sa.Column("document_id", sa.Text(), primary_key=True), sa.Column("title", sa.Text(), nullable=False), sa.Column("organization", sa.Text(), nullable=False), sa.Column("version", sa.Text()), sa.Column("effective_date", sa.Text()), sa.Column("source_reference", sa.Text()), sa.Column("filename", sa.Text(), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False), sa.Column("uploaded_by", sa.Text(), nullable=False), sa.Column("chunk_count", sa.Integer(), nullable=False))
    op.create_table("document_chunks", sa.Column("chunk_id", sa.Text(), primary_key=True), sa.Column("document_id", sa.Text(), sa.ForeignKey("safety_documents.document_id"), nullable=False), sa.Column("section", sa.Text()), sa.Column("page", sa.Integer()), sa.Column("text", sa.Text(), nullable=False), sa.Column("embedding", sa.Text(), nullable=False), sa.Column("embedding_model", sa.Text(), nullable=False))
    op.create_table("safety_alerts", sa.Column("alert_id", sa.Text(), primary_key=True), sa.Column("report_id", sa.Text(), sa.ForeignKey("safety_reports.report_id")), sa.Column("cluster_id", sa.Integer()), sa.Column("alert_type", sa.Text(), nullable=False), sa.Column("severity", sa.Text(), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("evidence", sa.Text()), sa.Column("status", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("decided_at", sa.DateTime(timezone=True)), sa.Column("decided_by", sa.Text()), sa.Column("decision_reason", sa.Text()))
    op.create_table("capas", sa.Column("capa_id", sa.Text(), primary_key=True), sa.Column("report_id", sa.Text(), sa.ForeignKey("safety_reports.report_id")), sa.Column("cluster_id", sa.Integer()), sa.Column("alert_id", sa.Text(), sa.ForeignKey("safety_alerts.alert_id")), *[sa.Column(name, sa.Text(), nullable=name not in {"title", "description", "action_type", "priority", "created_by", "created_by_role", "status"}) for name in ("title", "description", "action_type", "priority", "owner_name", "owner_role", "created_by", "created_by_role", "status", "completion_note", "verification_note", "verified_by")], sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("due_date", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.create_table("capa_evidence", sa.Column("evidence_id", sa.Text(), primary_key=True), sa.Column("capa_id", sa.Text(), sa.ForeignKey("capas.capa_id"), nullable=False), sa.Column("evidence_type", sa.Text(), nullable=False), sa.Column("reference", sa.Text()), sa.Column("note", sa.Text(), nullable=False), sa.Column("added_by", sa.Text(), nullable=False), sa.Column("added_by_role", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for table, column in (
        ("safety_reports", "report_id"), ("historical_analyses", "report_id"),
        ("historical_analyses", "status"), ("historical_analyses", "risk_level"),
        ("historical_analyses", "cluster_id"), ("hse_reviews", "report_id"),
        ("hse_reviews", "review_status"), ("hse_reviews", "created_at"),
        ("audit_events", "timestamp"), ("audit_events", "actor_name"),
        ("audit_events", "actor_role"), ("audit_events", "event_type"),
        ("audit_events", "entity_type"), ("audit_events", "entity_id"),
        ("document_chunks", "document_id"), ("safety_alerts", "report_id"),
        ("safety_alerts", "cluster_id"), ("safety_alerts", "alert_type"),
        ("safety_alerts", "severity"), ("safety_alerts", "status"),
        ("capas", "report_id"), ("capas", "cluster_id"), ("capas", "priority"),
        ("capas", "owner_name"), ("capas", "created_at"), ("capas", "due_date"),
        ("capas", "status"), ("capa_evidence", "capa_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for name in ("capa_evidence", "capas", "safety_alerts", "document_chunks", "safety_documents", "audit_events", "hse_reviews", "historical_analyses", "safety_reports"):
        op.drop_table(name)
