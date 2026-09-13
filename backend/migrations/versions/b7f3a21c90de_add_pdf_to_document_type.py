"""add_pdf_to_document_type

Revision ID: b7f3a21c90de
Revises: 9421176104ed
Create Date: 2026-09-04 02:30:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7f3a21c90de'
down_revision: Union[str, None] = '9421176104ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Append 'PDF' to the PostgreSQL document_type enum
    op.execute("ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'PDF'")


def downgrade() -> None:
    # 1. Inspect whether any PDF documents currently exist
    bind = op.get_bind()
    pdf_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM safety_documents WHERE document_type = 'PDF'")
    ).scalar()

    # 2. Abort if PDF documents are present to prevent data loss & orphaned ChromaDB vectors
    if pdf_count > 0:
        raise RuntimeError(
            f"Cannot downgrade migration: {pdf_count} PDF safety document(s) exist in the database. "
            "To prevent orphaned ChromaDB vector embeddings and permanent data loss, all PDF documents "
            "and their corresponding ChromaDB vectors must be removed through the application cleanup "
            "path before downgrading this migration."
        )

    # 3. Only if zero PDF records exist, safely revert to the original enum
    op.execute("CREATE TYPE document_type_old AS ENUM ('TXT', 'MARKDOWN')")
    op.execute(
        "ALTER TABLE safety_documents "
        "ALTER COLUMN document_type TYPE document_type_old "
        "USING (document_type::text::document_type_old)"
    )
    op.execute("DROP TYPE document_type")
    op.execute("ALTER TYPE document_type_old RENAME TO document_type")
