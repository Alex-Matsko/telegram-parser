"""Parsing tasks: process raw messages into structured offers."""
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def parse_pending_messages(self):
    """
    Periodic task: parse all unprocessed raw messages.
    Runs every 5 minutes via Celery Beat.
    """
    try:
        result = _run_async(_parse_pending_messages_async())
        return result
    except Exception as exc:
        logger.error(f"Parse task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task
def parse_single_message(message_id: int):
    """Parse a single raw message."""
    try:
        result = _run_async(_parse_single_message_async(message_id))
        return result
    except Exception as exc:
        logger.error(f"Parse single message {message_id} failed: {exc}")
        return {"error": str(exc)}


async def _parse_pending_messages_async() -> dict:
    """Parse all pending raw messages."""
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source

    stats = {"processed": 0, "parsed": 0, "failed": 0, "needs_review": 0}

    async with get_isolated_session() as session:
        # Get unprocessed messages (batch of 100)
        result = await session.execute(
            select(RawMessage)
            .where(RawMessage.parse_status == "pending")
            .order_by(RawMessage.created_at)
            .limit(100)
        )
        messages = result.scalars().all()

        if not messages:
            logger.debug("No pending messages to parse")
            return stats

        logger.info(f"Parsing {len(messages)} pending messages")

        for msg in messages:
            try:
                # Get source info for parsing strategy
                source_result = await session.execute(
                    select(Source).where(Source.id == msg.source_id)
                )
                source = source_result.scalar_one_or_none()
                parsing_strategy = source.parsing_strategy if source else "auto"
                supplier_id = source.supplier_id if source else None

                parse_result = await _process_single_message(
                    session=session,
                    message=msg,
                    parsing_strategy=parsing_strategy,
                    supplier_id=supplier_id,
                    confidence_threshold=settings.parser_confidence_threshold,
                )

                stats["processed"] += 1
                if parse_result == "parsed":
                    stats["parsed"] += 1
                elif parse_result == "needs_review":
                    stats["needs_review"] += 1
                else:
                    stats["failed"] += 1

            except Exception as e:
                logger.error(f"Error parsing message {msg.id}: {e}")
                msg.parse_status = "failed"
                msg.parse_error = str(e)[:1000]
                msg.is_processed = True
                stats["processed"] += 1
                stats["failed"] += 1

        await session.commit()

    logger.info(f"Parsing complete: {stats}")
    return stats


async def _parse_single_message_async(message_id: int) -> dict:
    """Parse a single message by ID."""
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source

    async with get_isolated_session() as session:
        result = await session.execute(
            select(RawMessage).where(RawMessage.id == message_id)
        )
        message = result.scalar_one_or_none()
        if not message:
            return {"error": f"Message {message_id} not found"}

        source_result = await session.execute(
            select(Source).where(Source.id == message.source_id)
        )
        source = source_result.scalar_one_or_none()
        parsing_strategy = source.parsing_strategy if source else "auto"
        supplier_id = source.supplier_id if source else None

        status = await _process_single_message(
            session=session,
            message=message,
            parsing_strategy=parsing_strategy,
            supplier_id=supplier_id,
            confidence_threshold=settings.parser_confidence_threshold,
        )

        await session.commit()
        return {"message_id": message_id, "status": status}


async def _process_single_message(
    session,
    message,
    parsing_strategy: str,
    supplier_id: int | None,
    confidence_threshold: float,
) -> str:
    """
    Process a single raw message through the parsing pipeline.

    Returns the final parse status: "parsed", "needs_review", or "failed".
    """
    from app.models.offer import Offer
    from app.models.price_history import PriceHistory
    from app.parser.llm_parser import parse_with_llm
    from app.parser.normalizer import normalize_and_match
    from app.parser.regex_parser import parse_message

    text = message.message_text
    offers_created = 0

    # Step 1: Try regex parser (unless strategy is "llm" only)
    parsed_offers = []
    if parsing_strategy in ("auto", "regex"):
        parse_result = parse_message(text)
        parsed_offers = parse_result.offers

    # Step 2: If regex gave no results or low confidence, try LLM
    if parsing_strategy == "auto" and (
        not parsed_offers
        or all(o.confidence < confidence_threshold for o in parsed_offers)
    ):
        llm_offers = await parse_with_llm(text)
        if llm_offers:
            parsed_offers = llm_offers

    if parsing_strategy == "llm":
        parsed_offers = await parse_with_llm(text)

    # Step 3: No offers parsed at all
    if not parsed_offers:
        message.parse_status = "failed"
        message.parse_error = "No offers could be extracted from the message"
        message.is_processed = True
        return "failed"

    # Step 4: Process each parsed offer
    any_success = False
    any_needs_review = False

    for parsed_offer in parsed_offers:
        # Normalize and match to product catalog
        product, match_confidence = await normalize_and_match(parsed_offer, session)

        if product is None or match_confidence < confidence_threshold:
            any_needs_review = True
            continue

        if parsed_offer.price is None or parsed_offer.price <= 0:
            any_needs_review = True
            continue

        # Determine supplier
        offer_supplier_id = supplier_id
        if not offer_supplier_id:
            # Try to find default supplier
            any_needs_review = True
            continue

        # Create or update offer
        # Mark old offers from same supplier for same product as not current
        from sqlalchemy import and_, select
        existing_offers_result = await session.execute(
            select(Offer).where(
                and_(
                    Offer.product_id == product.id,
                    Offer.supplier_id == offer_supplier_id,
                    Offer.is_current == True,  # noqa: E712
                )
            )
        )
        existing_offers = existing_offers_result.scalars().all()
        for old_offer in existing_offers:
            old_offer.is_current = False

        # Create new offer
        offer = Offer(
            supplier_id=offer_supplier_id,
            product_id=product.id,
            raw_message_id=message.id,
            price=Decimal(str(parsed_offer.price)),
            currency=parsed_offer.currency,
            detected_confidence=match_confidence,
            is_current=True,
        )
        session.add(offer)
        await session.flush()

        # Record price history
        history_entry = PriceHistory(
            offer_id=offer.id,
            supplier_id=offer_supplier_id,
            product_id=product.id,
            price=Decimal(str(parsed_offer.price)),
            currency=parsed_offer.currency,
        )
        session.add(history_entry)

        offers_created += 1
        any_success = True

    # Step 5: Set final status
    if any_success:
        message.parse_status = "parsed"
        message.is_processed = True
        status = "parsed"
    elif any_needs_review:
        message.parse_status = "needs_review"
        message.parse_error = "Low confidence or missing supplier"
        message.is_processed = True
        status = "needs_review"
    else:
        message.parse_status = "failed"
        message.parse_error = "Failed to create any offers"
        message.is_processed = True
        status = "failed"

    await session.flush()
    return status
