"""make raw_messages.source_id nullable

Revision ID: 0002_nullable_source_id
Revises: 
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_nullable_source_id'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make source_id nullable so we can keep messages after source deletion
    op.alter_column(
        'raw_messages',
        'source_id',
        existing_type=sa.Integer(),
        nullable=True,
    )
    # Drop the unique constraint that includes source_id (recreate as partial)
    op.drop_constraint('uq_source_message', 'raw_messages', type_='unique')
    op.create_unique_constraint(
        'uq_source_message',
        'raw_messages',
        ['source_id', 'telegram_message_id'],
    )


def downgrade() -> None:
    op.alter_column(
        'raw_messages',
        'source_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
