"""add channel_url to sources

Revision ID: 0005
Revises: 0004_pending_index
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004_pending_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('channel_url', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'channel_url')
