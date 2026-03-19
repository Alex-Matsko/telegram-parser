"""Add partial index on raw_messages for pending parse status

Revision ID: 0004_pending_index
Revises: 0003_nullable_source_id
Create Date: 2026-03-19

This index dramatically speeds up the batch query in parse.py:
    SELECT ... FROM raw_messages
    WHERE parse_status = 'pending'
    ORDER BY created_at
    LIMIT 100

The partial index (WHERE parse_status = 'pending') stays small because
parsed/failed rows are excluded — only the active queue is indexed.
"""
from alembic import op

revision = '0004_pending_index'
down_revision = '0003_nullable_source_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_messages_pending
        ON raw_messages (parse_status, created_at)
        WHERE parse_status = 'pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_raw_messages_pending")
