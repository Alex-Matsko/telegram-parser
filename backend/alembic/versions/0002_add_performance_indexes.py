"""Add performance indexes for frequent query patterns.

Revision ID: 0002
Revises: 001_initial
Create Date: 2026-03-18
"""
from alembic import op

revision = "0002"
down_revision = "001_initial"  # exact revision from 001_initial_schema.py
branch_labels = None
depends_on = None


def upgrade() -> None:
    # raw_messages: main filter in parse task (not in initial schema)
    op.create_index(
        "ix_raw_messages_parse_status_created",
        "raw_messages",
        ["parse_status", "created_at"],
    )
    # price_history by captured_at (initial schema has product+time and supplier+product,
    # but not supplier+captured_at separately)
    op.create_index(
        "ix_price_history_supplier_captured",
        "price_history",
        ["supplier_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_messages_parse_status_created", table_name="raw_messages")
    op.drop_index("ix_price_history_supplier_captured", table_name="price_history")
