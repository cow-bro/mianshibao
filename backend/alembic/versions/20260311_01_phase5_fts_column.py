"""Phase 5: Add tsvector full-text search column to knowledge_point."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260311_01"
down_revision: str = "20260310_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_point ADD COLUMN IF NOT EXISTS search_vector tsvector;"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_point_search_vector_gin
        ON knowledge_point
        USING gin (search_vector);
        """
    )
    # Backfill existing rows
    op.execute(
        """
        UPDATE knowledge_point
        SET search_vector = to_tsvector(
            'simple',
            coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(array_to_string(tags, ' '), '')
        )
        WHERE search_vector IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_point_search_vector_gin")
    op.execute("ALTER TABLE knowledge_point DROP COLUMN IF EXISTS search_vector;")
