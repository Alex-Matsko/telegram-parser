"""Add performance indexes for frequent query patterns.

Revision ID: 0002
Revises: 0001_initial_schema
Create Date: 2026-03-18
"""
from alembic import op

revision = "0002"
down_revision = "0001"  # links to 001_initial_schema.py
branch_labels = None
depends_on = None


def upgrade() -> None:
    # raw_messages: most common filter in parse task
    op.create_index(
        "ix_raw_messages_parse_status_created",
        "raw_messages",
        ["parse_status", "created_at"],
    )
    # offers: is_current filter used in price list and parse task
    op.create_index(
        "ix_offers_is_current",
        "offers",
        ["is_current"],
    )
    # offers: composite index for supplier+product lookups
    op.create_index(
        "ix_offers_product_supplier",
        "offers",
        ["product_id", "supplier_id"],
    )
    # price_history: used in 3-day history queries (TZ 4.7)
    op.create_index(
        "ix_price_history_product_captured",
        "price_history",
        ["product_id", "captured_at"],
    )
    op.create_index(
        "ix_price_history_supplier_captured",
        "price_history",
        ["supplier_id", "captured_at"],
    )
    # product_catalog: SKU lookup
    op.create_index(
        "ix_product_catalog_brand_model",
        "product_catalog",
        ["brand", "model"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_messages_parse_status_created", table_name="raw_messages")
    op.drop_index("ix_offers_is_current", table_name="offers")
    op.drop_index("ix_offers_product_supplier", table_name="offers")
    op.drop_index("ix_price_history_product_captured", table_name="price_history")
    op.drop_index("ix_price_history_supplier_captured", table_name="price_history")
    op.drop_index("ix_product_catalog_brand_model", table_name="product_catalog")
