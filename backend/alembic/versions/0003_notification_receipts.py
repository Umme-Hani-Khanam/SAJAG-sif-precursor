"""Add per-recipient notification read receipts.

Revision ID: 0003_notification_receipts
Revises: 0002_phase3a_platform
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_notification_receipts"
down_revision = "0002_phase3a_platform"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_reads",
        sa.Column("receipt_id", sa.Text(), primary_key=True),
        sa.Column(
            "notification_id", sa.Text(),
            sa.ForeignKey("notifications.notification_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reader_key", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("notification_id", "reader_key", name="uq_notification_reader"),
    )
    op.create_index("ix_notification_reads_notification_id", "notification_reads", ["notification_id"])
    op.create_index("ix_notification_reads_reader_key", "notification_reads", ["reader_key"])
    op.create_index("ix_notification_reads_read_at", "notification_reads", ["read_at"])


def downgrade():
    op.drop_table("notification_reads")
