"""Add knowledge category tree, bookmarks, learning progress, and personal library fields."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260317_01"
down_revision: str = "20260313_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_category",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["knowledge_category.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_knowledge_category_id"), "knowledge_category", ["id"], unique=False)
    op.create_index("ix_knowledge_category_subject", "knowledge_category", ["subject"], unique=False)

    op.add_column("knowledge_point", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column("knowledge_point", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_knowledge_point_category_id", "knowledge_point", "knowledge_category", ["category_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_knowledge_point_owner_user_id", "knowledge_point", "user", ["owner_user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_knowledge_point_category_id", "knowledge_point", ["category_id"], unique=False)
    op.create_index("ix_knowledge_point_owner_user_id", "knowledge_point", ["owner_user_id"], unique=False)

    op.create_table(
        "knowledge_bookmark",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_point.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_bookmark"),
    )
    op.create_index(op.f("ix_knowledge_bookmark_id"), "knowledge_bookmark", ["id"], unique=False)
    op.create_index("ix_knowledge_bookmark_user_id", "knowledge_bookmark", ["user_id"], unique=False)
    op.create_index("ix_knowledge_bookmark_knowledge_point_id", "knowledge_bookmark", ["knowledge_point_id"], unique=False)

    op.create_table(
        "knowledge_learning_progress",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UNREAD", "READING", "MASTERED", name="knowledge_learning_status", native_enum=False),
            nullable=False,
            server_default=sa.text("'UNREAD'"),
        ),
        sa.Column("read_duration_seconds", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_point.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_learning_progress"),
    )
    op.create_index(op.f("ix_knowledge_learning_progress_id"), "knowledge_learning_progress", ["id"], unique=False)
    op.create_index("ix_knowledge_learning_progress_user_id", "knowledge_learning_progress", ["user_id"], unique=False)
    op.create_index("ix_knowledge_learning_progress_knowledge_point_id", "knowledge_learning_progress", ["knowledge_point_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_learning_progress_knowledge_point_id", table_name="knowledge_learning_progress")
    op.drop_index("ix_knowledge_learning_progress_user_id", table_name="knowledge_learning_progress")
    op.drop_index(op.f("ix_knowledge_learning_progress_id"), table_name="knowledge_learning_progress")
    op.drop_table("knowledge_learning_progress")

    op.drop_index("ix_knowledge_bookmark_knowledge_point_id", table_name="knowledge_bookmark")
    op.drop_index("ix_knowledge_bookmark_user_id", table_name="knowledge_bookmark")
    op.drop_index(op.f("ix_knowledge_bookmark_id"), table_name="knowledge_bookmark")
    op.drop_table("knowledge_bookmark")

    op.drop_index("ix_knowledge_point_owner_user_id", table_name="knowledge_point")
    op.drop_index("ix_knowledge_point_category_id", table_name="knowledge_point")
    op.drop_constraint("fk_knowledge_point_owner_user_id", "knowledge_point", type_="foreignkey")
    op.drop_constraint("fk_knowledge_point_category_id", "knowledge_point", type_="foreignkey")
    op.drop_column("knowledge_point", "owner_user_id")
    op.drop_column("knowledge_point", "category_id")

    op.drop_index("ix_knowledge_category_subject", table_name="knowledge_category")
    op.drop_index(op.f("ix_knowledge_category_id"), table_name="knowledge_category")
    op.drop_table("knowledge_category")
