"""Add partial index on raw_messages for pending parse status

Revision ID: 0004_pending_index
Revises: 0003_nullable_source_id
Create Date: 2026-03-19

Note: CONCURRENTLY is not used here because Alembic runs migrations
inside a transaction block (asyncpg does not support CONCURRENTLY
inside transactions). The table is small at migration time so a regular
CREATE INDEX is safe and fast.
"""
from alembic import op

revision = '0004_pending_index'
down_revision = '0003_nullable_source_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_messages_pending
        ON raw_messages (parse_status, created_at)
        WHERE parse_status = 'pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_raw_messages_pending")
