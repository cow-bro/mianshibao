"""Add scope column to knowledge_point for GENERAL/POSITION classification."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260311_03"
down_revision: str = "20260311_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_point",
        sa.Column(
            "scope",
            sa.Enum("GENERAL", "POSITION", name="knowledge_scope", native_enum=False),
            nullable=False,
            server_default=sa.text("'GENERAL'"),
        ),
    )
    op.create_index("ix_knowledge_point_scope", "knowledge_point", ["scope"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_point_scope", table_name="knowledge_point")
    op.drop_column("knowledge_point", "scope")
