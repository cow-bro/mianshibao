"""Stage 6 interview engine schema updates.

Revision ID: 20260312_01
Revises: 20260311_03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260312_01"
down_revision: str | None = "20260311_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_message",
        sa.Column("question_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("interview_message", sa.Column("stage", sa.String(length=50), nullable=True))

    op.add_column(
        "interview_session",
        sa.Column("interview_start_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_session",
        sa.Column("interview_duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "interview_session",
        sa.Column("max_interview_duration", sa.Integer(), nullable=False, server_default=sa.text("3600")),
    )
    op.add_column(
        "interview_session",
        sa.Column("max_total_questions", sa.Integer(), nullable=False, server_default=sa.text("12")),
    )
    op.add_column(
        "interview_session",
        sa.Column("max_resume_dig_questions", sa.Integer(), nullable=False, server_default=sa.text("4")),
    )
    op.add_column(
        "interview_session",
        sa.Column("max_tech_qa_questions", sa.Integer(), nullable=False, server_default=sa.text("6")),
    )
    op.add_column(
        "interview_session",
        sa.Column("is_human_intervention_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("interview_session", sa.Column("human_intervention_status", sa.String(length=50), nullable=True))
    op.add_column("interview_session", sa.Column("human_operator_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_interview_session_human_operator_id_user",
        "interview_session",
        "user",
        ["human_operator_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "interview_report",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_company", sa.String(length=100), nullable=True),
        sa.Column("target_position", sa.String(length=100), nullable=True),
        sa.Column("interview_duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("professional_knowledge_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("project_experience_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("logical_thinking_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("communication_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("position_match_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("highlights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("improvement_suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_knowledge_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("interview_summary", sa.Text(), nullable=False),
        sa.Column("answer_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_interview_report_id"), "interview_report", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_report_id"), table_name="interview_report")
    op.drop_table("interview_report")

    op.drop_constraint("fk_interview_session_human_operator_id_user", "interview_session", type_="foreignkey")
    op.drop_column("interview_session", "human_operator_id")
    op.drop_column("interview_session", "human_intervention_status")
    op.drop_column("interview_session", "is_human_intervention_enabled")
    op.drop_column("interview_session", "max_tech_qa_questions")
    op.drop_column("interview_session", "max_resume_dig_questions")
    op.drop_column("interview_session", "max_total_questions")
    op.drop_column("interview_session", "max_interview_duration")
    op.drop_column("interview_session", "interview_duration_seconds")
    op.drop_column("interview_session", "interview_start_time")

    op.drop_column("interview_message", "stage")
    op.drop_column("interview_message", "question_index")
