"""Initial schema - create all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_suppliers_name"),
    )

    # Bot scenarios
    op.create_table(
        "bot_scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bot_name", sa.String(255), nullable=False),
        sa.Column("scenario_name", sa.String(255), nullable=False),
        sa.Column("steps_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Sources
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "poll_interval_minutes", sa.Integer(), server_default="30", nullable=False
        ),
        sa.Column(
            "parsing_strategy", sa.String(20), server_default="auto", nullable=False
        ),
        sa.Column("bot_scenario_id", sa.Integer(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id", name="uq_sources_telegram_id"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["bot_scenario_id"], ["bot_scenarios.id"]),
    )

    # Product catalog
    op.create_table(
        "product_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("line", sa.String(100), nullable=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("generation", sa.String(50), nullable=True),
        sa.Column("memory", sa.String(20), nullable=True),
        sa.Column("color", sa.String(100), nullable=True),
        sa.Column("sim_type", sa.String(20), nullable=True),
        sa.Column("region", sa.String(20), nullable=True),
        sa.Column(
            "condition", sa.String(20), server_default="new", nullable=False
        ),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("sku_key", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_key", name="uq_product_catalog_sku_key"),
    )
    op.create_index(
        "ix_product_catalog_brand_model", "product_catalog", ["brand", "model"]
    )
    op.create_index("ix_product_catalog_category", "product_catalog", ["category"])
    op.create_index("ix_product_catalog_sku_key", "product_catalog", ["sku_key"])

    # Raw messages
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column(
            "raw_payload", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "is_processed", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "parse_status", sa.String(20), server_default="pending", nullable=False
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.UniqueConstraint(
            "source_id", "telegram_message_id", name="uq_source_message"
        ),
    )

    # Offers
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("raw_message_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="RUB", nullable=False),
        sa.Column("availability", sa.String(50), nullable=True),
        sa.Column(
            "detected_confidence", sa.Float(), server_default="1.0", nullable=False
        ),
        sa.Column(
            "is_current", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["product_catalog.id"]),
        sa.ForeignKeyConstraint(["raw_message_id"], ["raw_messages.id"]),
    )
    op.create_index(
        "ix_offers_product_supplier", "offers", ["product_id", "supplier_id"]
    )
    op.create_index("ix_offers_is_current", "offers", ["is_current"])

    # Price history
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="RUB", nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["product_catalog.id"]),
    )
    op.create_index(
        "ix_price_history_product_time", "price_history", ["product_id", "captured_at"]
    )
    op.create_index(
        "ix_price_history_supplier_product",
        "price_history",
        ["supplier_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_table("offers")
    op.drop_table("raw_messages")
    op.drop_table("product_catalog")
    op.drop_table("sources")
    op.drop_table("bot_scenarios")
    op.drop_table("suppliers")
