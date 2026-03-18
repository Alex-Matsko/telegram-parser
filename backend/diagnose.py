"""
Diagnostic script — run inside the backend container to check the full pipeline.

Usage:
    docker exec -it <backend-container> python diagnose.py
"""
import asyncio
from sqlalchemy import select, func, and_


async def diagnose():
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.product_catalog import ProductCatalog
    from app.models.offer import Offer
    from app.models.source import Source
    from app.models.supplier import Supplier

    async with get_isolated_session() as session:
        print("=" * 65)
        print("  TELEGRAM PARSER — PIPELINE DIAGNOSTICS")
        print("=" * 65)

        # --- Suppliers ---
        suppliers_result = await session.execute(select(Supplier))
        suppliers = suppliers_result.scalars().all()
        print(f"\n🏪 SUPPLIERS ({len(suppliers)}):")
        if not suppliers:
            print("  ⚠️  NO SUPPLIERS FOUND!")
            print("  → Create one: POST /api/suppliers  {name: '...', is_active: true}")
        for s in suppliers:
            status = "✅" if s.is_active else "❌"
            print(f"  {status} [{s.id}] {s.name}")

        # --- Sources ---
        sources_result = await session.execute(select(Source))
        sources = sources_result.scalars().all()
        print(f"\n📡 SOURCES ({len(sources)}):")
        if not sources:
            print("  ⚠️  NO SOURCES FOUND! Add via POST /api/sources")
        for s in sources:
            active = "✅" if s.is_active else "❌"
            has_supplier = "✅" if s.supplier_id else "❌ NO SUPPLIER!"
            last_read = s.last_read_at.strftime("%d.%m %H:%M") if s.last_read_at else "never"
            error_info = f" | ⚠️ errors: {s.error_count}" if (s.error_count or 0) > 0 else ""
            print(
                f"  {active} [{s.id}] {s.source_name} "
                f"(type={s.type}) | supplier: {has_supplier} "
                f"| last_read: {last_read}{error_info}"
            )

        # --- Raw messages ---
        print("\n📨 RAW MESSAGES:")
        for status in ["pending", "parsed", "needs_review", "failed"]:
            cnt = await session.scalar(
                select(func.count(RawMessage.id)).where(RawMessage.parse_status == status)
            )
            icon = {"pending": "⏳", "parsed": "✅", "needs_review": "🔍", "failed": "❌"}.get(status, "?")
            print(f"  {icon} {status.upper()}: {cnt}")

        total_msgs = await session.scalar(select(func.count(RawMessage.id)))
        print(f"  📊 TOTAL: {total_msgs}")

        # --- Product catalog ---
        product_count = await session.scalar(select(func.count(ProductCatalog.id)))
        print(f"\n📦 PRODUCTS IN CATALOG: {product_count}")

        if product_count and product_count > 0:
            recent_products = await session.execute(
                select(ProductCatalog.normalized_name)
                .order_by(ProductCatalog.id.desc())
                .limit(5)
            )
            for row in recent_products.scalars():
                print(f"  · {row}")

        # --- Offers ---
        current_offers = await session.scalar(
            select(func.count(Offer.id)).where(Offer.is_current == True)  # noqa: E712
        )
        total_offers = await session.scalar(select(func.count(Offer.id)))
        print(f"\n💰 OFFERS: {current_offers} current / {total_offers} total")

        # --- Last activity ---
        last_msg_date = await session.scalar(
            select(RawMessage.created_at).order_by(RawMessage.created_at.desc()).limit(1)
        )
        print(f"\n🕐 LAST MESSAGE COLLECTED: {last_msg_date or 'Never'}")

        last_offer_date = await session.scalar(
            select(Offer.created_at).order_by(Offer.created_at.desc()).limit(1)
        )
        print(f"🕐 LAST OFFER CREATED:    {last_offer_date or 'Never'}")

        # --- Diagnosis and recommendations ---
        print("\n" + "=" * 65)
        print("💡 RECOMMENDATIONS:")
        issues = []

        if not suppliers:
            issues.append("1️⃣  Create a Supplier: POST /api/suppliers")

        sources_no_supplier = [s for s in sources if not s.supplier_id]
        if sources_no_supplier:
            names = ", ".join(s.source_name for s in sources_no_supplier)
            issues.append(
                f"2️⃣  Link Supplier to Source(s): {names}\n"
                f"     PUT /api/sources/<id>  {{\"supplier_id\": <id>}}"
            )

        pending_cnt = await session.scalar(
            select(func.count(RawMessage.id)).where(RawMessage.parse_status == "pending")
        )
        if pending_cnt and pending_cnt > 0:
            issues.append(
                f"3️⃣  {pending_cnt} pending messages — trigger parse:\n"
                f"     docker exec <backend> python -c \""
                f"from app.tasks.parse import parse_pending_messages; "
                f"parse_pending_messages.delay()\""
            )

        needs_review_cnt = await session.scalar(
            select(func.count(RawMessage.id)).where(RawMessage.parse_status == "needs_review")
        )
        if needs_review_cnt and needs_review_cnt > 0:
            issues.append(
                f"4️⃣  {needs_review_cnt} messages need review — check /api/unresolved"
            )

        sources_with_errors = [s for s in sources if (s.error_count or 0) > 0]
        if sources_with_errors:
            for s in sources_with_errors:
                issues.append(
                    f"5️⃣  Source '{s.source_name}' has {s.error_count} errors: {s.last_error}"
                )

        if not issues:
            print("  ✅ Everything looks good! Pipeline is working.")
        else:
            for issue in issues:
                print(f"  {issue}")

        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(diagnose())
