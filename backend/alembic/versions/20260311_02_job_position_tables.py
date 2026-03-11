"""Add job_category, job_position, position_knowledge tables and interview_session.position_id FK."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260311_02"
down_revision: str = "20260311_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── job_category ──
    op.create_table(
        "job_category",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_job_category_id"), "job_category", ["id"], unique=False)

    # ── job_position ──
    op.create_table(
        "job_position",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "level",
            sa.Enum("INTERN", "JUNIOR", "MID", "SENIOR", name="position_level", native_enum=False),
            nullable=False,
            server_default=sa.text("'JUNIOR'"),
        ),
        sa.Column("required_skills", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("salary_range", sa.String(length=50), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["job_category.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_job_position_id"), "job_position", ["id"], unique=False)
    op.create_index("ix_job_position_category_id", "job_position", ["category_id"], unique=False)

    # ── position_knowledge (M:N 关联表) ──
    op.create_table(
        "position_knowledge",
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column(
            "relevance",
            sa.Enum("CORE", "IMPORTANT", "OPTIONAL", name="knowledge_relevance", native_enum=False),
            nullable=False,
            server_default=sa.text("'IMPORTANT'"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["position_id"], ["job_position.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_point.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position_id", "knowledge_point_id", name="uq_position_knowledge"),
    )
    op.create_index(op.f("ix_position_knowledge_id"), "position_knowledge", ["id"], unique=False)

    # ── interview_session 添加 position_id 外键 ──
    op.add_column(
        "interview_session",
        sa.Column("position_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_session_position_id",
        "interview_session",
        "job_position",
        ["position_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_interview_session_position_id", "interview_session", type_="foreignkey")
    op.drop_column("interview_session", "position_id")

    op.drop_index(op.f("ix_position_knowledge_id"), table_name="position_knowledge")
    op.drop_table("position_knowledge")

    op.drop_index("ix_job_position_category_id", table_name="job_position")
    op.drop_index(op.f("ix_job_position_id"), table_name="job_position")
    op.drop_table("job_position")

    op.drop_index(op.f("ix_job_category_id"), table_name="job_category")
    op.drop_table("job_category")
