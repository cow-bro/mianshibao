"""Add file_hash to resume.

Revision ID: 20260313_01
Revises: 20260312_01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260313_01"
down_revision: str | None = "20260312_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resume", sa.Column("file_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_resume_file_hash", "resume", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_resume_file_hash", table_name="resume")
    op.drop_column("resume", "file_hash")