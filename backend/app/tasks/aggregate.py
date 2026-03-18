"""Aggregation tasks: refresh price list calculations and mark stale offers."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a fresh event loop (safe for Celery prefork)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def refresh_price_list(self):
    """
    Periodic task: refresh price list calculations.
    - Marks stale offers (older than 3 days) as not current.
    - Deduplicates same-product/same-supplier offers.
    Runs every 10 minutes via Celery Beat.
    """
    try:
        result = _run_async(_refresh_price_list_async())
        return result
    except Exception as exc:
        logger.error(f"Refresh price list failed: {exc}")
        raise self.retry(exc=exc)


async def _refresh_price_list_async() -> dict:
    """Perform price list refresh operations."""
    from sqlalchemy import and_, func, select, update

    from app.database import get_isolated_session
    from app.models.offer import Offer

    stats = {"stale_marked": 0}

    async with get_isolated_session() as session:
        # Mark offers older than 3 days as not current
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=3)

        result = await session.execute(
            update(Offer)
            .where(
                and_(
                    Offer.is_current == True,  # noqa: E712
                    Offer.updated_at < stale_cutoff,
                )
            )
            .values(is_current=False)
        )
        stats["stale_marked"] = result.rowcount

        # For products with multiple current offers from same supplier,
        # keep only the most recent one
        dupe_subq = (
            select(
                Offer.product_id,
                Offer.supplier_id,
                func.count(Offer.id).label("cnt"),
            )
            .where(Offer.is_current == True)  # noqa: E712
            .group_by(Offer.product_id, Offer.supplier_id)
            .having(func.count(Offer.id) > 1)
            .subquery()
        )

        dupe_pairs = (await session.execute(
            select(dupe_subq.c.product_id, dupe_subq.c.supplier_id)
        )).all()

        deduped = 0
        for product_id, supplier_id in dupe_pairs:
            offers_result = await session.execute(
                select(Offer)
                .where(
                    and_(
                        Offer.product_id == product_id,
                        Offer.supplier_id == supplier_id,
                        Offer.is_current == True,  # noqa: E712
                    )
                )
                .order_by(Offer.updated_at.desc())
            )
            offers = offers_result.scalars().all()

            # Mark all but the newest as not current
            for offer in offers[1:]:
                offer.is_current = False
                deduped += 1

        stats["deduped"] = deduped

        await session.commit()

    logger.info(f"Price list refresh complete: {stats}")
    return stats
