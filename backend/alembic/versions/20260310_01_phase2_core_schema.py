"""Phase 2 core schema with pgvector support."""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260310_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "resume_template",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "quality_level",
            sa.Enum("EXCELLENT", "POOR", name="resume_quality_level", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_template_id"), "resume_template", ["id"], unique=False)

    op.create_table(
        "user",
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("avatar_url", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum("USER", "VIP", "ADMIN", name="user_role", native_enum=False),
            nullable=False,
            server_default=sa.text("'USER'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_user_id"), "user", ["id"], unique=False)

    op.create_table(
        "knowledge_point",
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            sa.Enum("KNOWLEDGE", "QUESTION", name="knowledge_point_type", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "difficulty",
            sa.Enum("EASY", "MEDIUM", "HARD", name="difficulty_level", native_enum=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("source_company", sa.String(length=100), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_point_id"), "knowledge_point", ["id"], unique=False)

    op.create_table(
        "resume",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("file_url", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("parsed_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("dimension_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggestions", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_id"), "resume", ["id"], unique=False)

    op.create_table(
        "interview_session",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("target_company", sa.String(length=100), nullable=True),
        sa.Column("target_position", sa.String(length=100), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("INIT", "ONGOING", "ENDED", name="interview_status", native_enum=False),
            nullable=False,
            server_default=sa.text("'INIT'"),
        ),
        sa.Column("current_stage", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resume.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_session_id"), "interview_session", ["id"], unique=False)

    op.create_table(
        "interview_message",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "INTERVIEWER",
                "CANDIDATE",
                name="interview_message_role",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_message_id"), "interview_message", ["id"], unique=False)

    op.create_table(
        "wrong_question",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column(
            "mastery_level",
            sa.Enum(
                "UNFAMILIAR",
                "FAMILIAR",
                "MASTERED",
                name="mastery_level",
                native_enum=False,
            ),
            nullable=False,
            server_default=sa.text("'UNFAMILIAR'"),
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_point.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wrong_question_id"), "wrong_question", ["id"], unique=False)

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_point_embedding_hnsw
        ON knowledge_point
        USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_point_embedding_hnsw")

    op.drop_index(op.f("ix_wrong_question_id"), table_name="wrong_question")
    op.drop_table("wrong_question")

    op.drop_index(op.f("ix_interview_message_id"), table_name="interview_message")
    op.drop_table("interview_message")

    op.drop_index(op.f("ix_interview_session_id"), table_name="interview_session")
    op.drop_table("interview_session")

    op.drop_index(op.f("ix_resume_id"), table_name="resume")
    op.drop_table("resume")

    op.drop_index(op.f("ix_knowledge_point_id"), table_name="knowledge_point")
    op.drop_table("knowledge_point")

    op.drop_index(op.f("ix_user_id"), table_name="user")
    op.drop_table("user")

    op.drop_index(op.f("ix_resume_template_id"), table_name="resume_template")
    op.drop_table("resume_template")
