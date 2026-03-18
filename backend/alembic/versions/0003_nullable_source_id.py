"""make raw_messages.source_id nullable

Revision ID: 0003_nullable_source_id
Revises: 0002
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_nullable_source_id'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'raw_messages',
        'source_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'raw_messages',
        'source_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
