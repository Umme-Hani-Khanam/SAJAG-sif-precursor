"""Phase 3A deployable-platform schema."""
from alembic import op
import sqlalchemy as sa

revision = "0002_phase3a_platform"
down_revision = "0001_phase2_baseline"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("users", sa.Column("user_id", sa.Text(), primary_key=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("email", sa.Text(), nullable=False, unique=True), sa.Column("username", sa.Text(), nullable=False, unique=True), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("role", sa.Text(), nullable=False), sa.Column("site_scope", sa.Text(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login", sa.DateTime(timezone=True)))
    op.create_table("auth_sessions", sa.Column("session_id", sa.Text(), primary_key=True), sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.Text(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("background_jobs", sa.Column("job_id", sa.Text(), primary_key=True), sa.Column("job_type", sa.Text(), nullable=False), sa.Column("status", sa.Text(), nullable=False), sa.Column("progress_current", sa.Integer(), nullable=False), sa.Column("progress_total", sa.Integer(), nullable=False), sa.Column("payload", sa.Text()), sa.Column("result", sa.Text()), sa.Column("error", sa.Text()), sa.Column("created_by_user_id", sa.Text(), sa.ForeignKey("users.user_id")), sa.Column("created_by_name", sa.Text(), nullable=False), sa.Column("site", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_table("notifications", sa.Column("notification_id", sa.Text(), primary_key=True), sa.Column("recipient_user_id", sa.Text(), sa.ForeignKey("users.user_id")), sa.Column("recipient_role", sa.Text()), sa.Column("recipient_site", sa.Text()), sa.Column("notification_type", sa.Text(), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("entity_type", sa.Text()), sa.Column("entity_id", sa.Text()), sa.Column("dedupe_key", sa.Text(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("read_at", sa.DateTime(timezone=True)))
    op.create_table("attachments", sa.Column("attachment_id", sa.Text(), primary_key=True), sa.Column("entity_type", sa.Text(), nullable=False), sa.Column("entity_id", sa.Text(), nullable=False), sa.Column("filename", sa.Text(), nullable=False), sa.Column("storage_key", sa.Text(), nullable=False, unique=True), sa.Column("media_type", sa.Text(), nullable=False), sa.Column("size", sa.Integer(), nullable=False), sa.Column("uploaded_by", sa.Text(), nullable=False), sa.Column("uploaded_by_user_id", sa.Text(), sa.ForeignKey("users.user_id")), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False), sa.Column("description", sa.Text()), sa.Column("sha256", sa.Text(), nullable=False))

    with op.batch_alter_table("safety_reports") as batch:
        batch.add_column(sa.Column("observed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("submitted_by_user_id", sa.Text()))
        batch.add_column(sa.Column("confidence_label", sa.Text()))
        batch.add_column(sa.Column("confidence_reasons", sa.Text()))
        batch.add_column(sa.Column("review_recommended", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("input_provenance", sa.Text()))
        batch.add_column(sa.Column("photo_findings", sa.Text()))
        batch.create_foreign_key("fk_report_submitter", "users", ["submitted_by_user_id"], ["user_id"])
    with op.batch_alter_table("capa_evidence") as batch:
        batch.add_column(sa.Column("attachment_id", sa.Text()))
        batch.create_foreign_key("fk_capa_evidence_attachment", "attachments", ["attachment_id"], ["attachment_id"])
    with op.batch_alter_table("safety_documents") as batch:
        batch.add_column(sa.Column("status", sa.Text(), nullable=False, server_default="APPROVED"))
        batch.add_column(sa.Column("review_date", sa.Text()))
        batch.add_column(sa.Column("approved_by", sa.Text()))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("supersedes_document_id", sa.Text()))
        batch.add_column(sa.Column("attachment_id", sa.Text()))
        batch.add_column(sa.Column("indexing_status", sa.Text(), nullable=False, server_default="completed"))
        batch.create_foreign_key("fk_document_supersedes", "safety_documents", ["supersedes_document_id"], ["document_id"])
        batch.create_foreign_key("fk_document_attachment", "attachments", ["attachment_id"], ["attachment_id"])

    vector_type = sa.Text()
    if postgres:
        from pgvector.sqlalchemy import Vector
        vector_type = Vector(384)
    op.add_column("historical_analyses", sa.Column("embedding_vector", vector_type))
    op.add_column("document_chunks", sa.Column("embedding_vector", vector_type))
    if postgres:
        op.execute("CREATE INDEX ix_historical_embedding_hnsw ON historical_analyses USING hnsw (embedding_vector vector_cosine_ops)")
        op.execute("CREATE INDEX ix_document_embedding_hnsw ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)")

    op.create_table("photo_analyses", sa.Column("photo_analysis_id", sa.Text(), primary_key=True), sa.Column("report_id", sa.Text(), sa.ForeignKey("safety_reports.report_id")), sa.Column("attachment_id", sa.Text(), sa.ForeignKey("attachments.attachment_id"), nullable=False), sa.Column("visible_hazards", sa.Text(), nullable=False), sa.Column("visible_controls", sa.Text(), nullable=False), sa.Column("possible_missing_controls", sa.Text(), nullable=False), sa.Column("possible_exposures", sa.Text(), nullable=False), sa.Column("image_summary", sa.Text(), nullable=False), sa.Column("confidence", sa.Text(), nullable=False), sa.Column("provider", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("validation_datasets", sa.Column("dataset_id", sa.Text(), primary_key=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("description", sa.Text()), sa.Column("created_by", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("case_count", sa.Integer(), nullable=False))
    op.create_table("validation_cases", sa.Column("case_id", sa.Text(), primary_key=True), sa.Column("dataset_id", sa.Text(), sa.ForeignKey("validation_datasets.dataset_id", ondelete="CASCADE"), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("site", sa.Text()), sa.Column("activity", sa.Text()), sa.Column("expected_hazard", sa.Text(), nullable=False), sa.Column("expected_exposure", sa.Text(), nullable=False), sa.Column("expected_critical_control", sa.Text(), nullable=False), sa.Column("expected_precursor", sa.Text(), nullable=False), sa.Column("expected_risk_level", sa.Text(), nullable=False))
    op.create_table("validation_runs", sa.Column("run_id", sa.Text(), primary_key=True), sa.Column("dataset_id", sa.Text(), sa.ForeignKey("validation_datasets.dataset_id"), nullable=False), sa.Column("status", sa.Text(), nullable=False), sa.Column("metrics", sa.Text(), nullable=False), sa.Column("confusion_matrix", sa.Text(), nullable=False), sa.Column("model_version", sa.Text(), nullable=False), sa.Column("scoring_version", sa.Text(), nullable=False), sa.Column("validation_timestamp", sa.DateTime(timezone=True), nullable=False))
    op.create_table("notification_preferences", sa.Column("preference_id", sa.Text(), primary_key=True), sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False), sa.Column("notification_type", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.UniqueConstraint("user_id", "notification_type", name="uq_notification_preference"))
    for table, column in (
        ("users", "email"), ("users", "username"), ("users", "role"), ("users", "active"),
        ("auth_sessions", "user_id"), ("auth_sessions", "token_hash"), ("auth_sessions", "expires_at"),
        ("background_jobs", "job_type"), ("background_jobs", "status"),
        ("background_jobs", "created_by_user_id"), ("background_jobs", "site"), ("background_jobs", "created_at"),
        ("notifications", "recipient_user_id"), ("notifications", "recipient_role"),
        ("notifications", "recipient_site"), ("notifications", "notification_type"),
        ("notifications", "entity_id"), ("notifications", "dedupe_key"),
        ("notifications", "created_at"), ("notifications", "read_at"),
        ("attachments", "entity_type"), ("attachments", "entity_id"),
        ("attachments", "uploaded_by_user_id"), ("attachments", "uploaded_at"),
        ("photo_analyses", "report_id"), ("validation_cases", "dataset_id"),
        ("validation_runs", "dataset_id"), ("validation_runs", "status"),
        ("validation_runs", "validation_timestamp"), ("notification_preferences", "user_id"),
    ):
        op.create_index(
            f"ix_{table}_{column}", table, [column],
            unique=(table, column) in {("users", "email"), ("users", "username"), ("auth_sessions", "token_hash"), ("notifications", "dedupe_key")},
        )
    for column in ("observed_at", "submitted_at", "submitted_by_user_id", "confidence_label", "review_recommended"):
        op.create_index(f"ix_safety_reports_{column}", "safety_reports", [column])
    for column in ("status", "review_date", "indexing_status"):
        op.create_index(f"ix_safety_documents_{column}", "safety_documents", [column])


def downgrade():
    for name in ("notification_preferences", "validation_runs", "validation_cases", "validation_datasets", "photo_analyses"):
        op.drop_table(name)
    op.drop_column("document_chunks", "embedding_vector")
    op.drop_column("historical_analyses", "embedding_vector")
    # Remaining destructive downgrade operations are deliberately omitted. Phase 3A
    # upgrades are data-preserving; production rollback should restore from backup.
