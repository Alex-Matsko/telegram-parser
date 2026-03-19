"""Add partial index on raw_messages for pending parse status

Revision ID: 0004_pending_index
Revises: 0003_nullable_source_id
Create Date: 2026-03-19

CREATE INDEX CONCURRENTLY cannot run inside a transaction block,
so this migration sets transaction=False.
"""
from alembic import op

revision = '0004_pending_index'
down_revision = '0003_nullable_source_id'
branch_labels = None
depends_on = None

# Required for CREATE INDEX CONCURRENTLY
transactional_ddl = False


def upgrade() -> None:
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_messages_pending
        ON raw_messages (parse_status, created_at)
        WHERE parse_status = 'pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_raw_messages_pending")
