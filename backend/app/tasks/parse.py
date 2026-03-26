"""Parsing tasks: process raw messages into structured offers."""
import asyncio
import logging
from decimal import Decimal

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=300,
    time_limit=360,
)
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
    """Parse all pending raw messages — batch of 100."""
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source
    from app.services.supplier_service import get_or_create_supplier_for_source

    stats = {
        "processed": 0, "parsed": 0, "failed": 0,
        "needs_review": 0, "skipped_unchanged": 0,
        "llm_calls": 0, "system_skipped": 0,
    }

    async with get_isolated_session() as session:
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

        source_ids = list({msg.source_id for msg in messages})
        sources_result = await session.execute(
            select(Source).where(Source.id.in_(source_ids))
        )
        sources_map = {s.id: s for s in sources_result.scalars().all()}

        for source in sources_map.values():
            if not source.supplier_id:
                await get_or_create_supplier_for_source(source, session)
        await session.flush()

        llm_calls_this_batch = 0
        max_llm_calls = getattr(settings, "llm_max_per_batch", 20)

        for msg in messages:
            try:
                source = sources_map.get(msg.source_id)
                parsing_strategy = source.parsing_strategy if source else "auto"
                supplier_id = source.supplier_id if source else None

                parse_result, skipped, used_llm, system_skip = await _process_single_message(
                    session=session,
                    message=msg,
                    parsing_strategy=parsing_strategy,
                    supplier_id=supplier_id,
                    confidence_threshold=settings.parser_confidence_threshold,
                    skip_unchanged=settings.skip_unchanged_prices,
                    llm_budget=max_llm_calls - llm_calls_this_batch,
                )

                if used_llm:
                    llm_calls_this_batch += 1

                stats["processed"] += 1
                stats["skipped_unchanged"] += skipped
                stats["llm_calls"] = llm_calls_this_batch
                stats["system_skipped"] += 1 if system_skip else 0

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
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source
    from app.services.supplier_service import get_or_create_supplier_for_source

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

        if source and not source.supplier_id:
            await get_or_create_supplier_for_source(source, session)
            await session.flush()

        supplier_id = source.supplier_id if source else None

        status, _, _, _ = await _process_single_message(
            session=session,
            message=message,
            parsing_strategy=parsing_strategy,
            supplier_id=supplier_id,
            confidence_threshold=settings.parser_confidence_threshold,
            skip_unchanged=settings.skip_unchanged_prices,
            llm_budget=1,
        )

        await session.commit()
        return {"message_id": message_id, "status": status}


async def _process_single_message(
    session,
    message,
    parsing_strategy: str,
    supplier_id: int | None,
    confidence_threshold: float,
    skip_unchanged: bool = True,
    llm_budget: int = 1,
) -> tuple[str, int, bool, bool]:
    """
    Returns: (status, skipped_unchanged_count, used_llm, system_skip)
    system_skip=True means message was filtered before regex/LLM.
    llm_budget=0 means skip LLM entirely (mark needs_review).
    """
    from app.models.offer import Offer
    from app.models.price_history import PriceHistory
    from app.parser.llm_parser import parse_with_llm
    from app.parser.normalizer import normalize_and_match
    from app.parser.regex_parser import is_obviously_not_price_message, parse_message

    text = message.message_text

    # ------------------------------------------------------------------ #
    # Pre-filter: системные сообщения бота, мусор без признаков цены      #
    # ------------------------------------------------------------------ #
    if is_obviously_not_price_message(text):
        logger.debug(f"Message {message.id} is not a price message — skipped (pre-filter)")
        message.parse_status = "failed"
        message.parse_error = "Not a price message (pre-filter)"
        message.is_processed = True
        await session.flush()
        return "failed", 0, False, True

    offers_created = 0
    skipped_unchanged = 0
    used_llm = False

    # Step 1: Regex parser
    parsed_offers = []
    if parsing_strategy in ("auto", "regex"):
        parse_result = parse_message(text)
        parsed_offers = parse_result.offers
        logger.debug(
            f"Regex parser: {len(parsed_offers)} offers, "
            f"unparsed lines: {len(parse_result.unparsed_lines)}"
        )

    # Step 2: LLM fallback
    needs_llm = (
        parsing_strategy == "auto"
        and (
            not parsed_offers
            or all(o.confidence < confidence_threshold for o in parsed_offers)
        )
    )

    if needs_llm:
        if llm_budget <= 0:
            logger.debug(f"LLM budget exhausted, skipping message {message.id} — needs_review")
            message.parse_status = "needs_review"
            message.parse_error = "LLM budget exhausted for this batch"
            message.is_processed = True
            return "needs_review", 0, False, False

        logger.debug(f"Falling back to LLM for message {message.id}")
        llm_offers = await parse_with_llm(text)
        used_llm = True
        if llm_offers:
            parsed_offers = llm_offers

    if parsing_strategy == "llm":
        if llm_budget > 0:
            parsed_offers = await parse_with_llm(text)
            used_llm = True
        else:
            message.parse_status = "needs_review"
            message.parse_error = "LLM budget exhausted for this batch"
            message.is_processed = True
            return "needs_review", 0, False, False

    # Step 3: No offers extracted
    if not parsed_offers:
        message.parse_status = "failed"
        message.parse_error = "No offers could be extracted from the message"
        message.is_processed = True
        return "failed", 0, used_llm, False

    # Step 4: Process each parsed offer
    any_success = False
    any_needs_review = False

    for parsed_offer in parsed_offers:
        if not supplier_id:
            any_needs_review = True
            logger.warning(f"Message {message.id}: supplier_id missing — needs_review")
            continue

        if parsed_offer.price is None or parsed_offer.price <= 0:
            logger.debug(f"Offer skipped: no valid price ({parsed_offer.price})")
            any_needs_review = True
            continue

        product, match_confidence = await normalize_and_match(parsed_offer, session)

        if product is None or match_confidence < confidence_threshold:
            logger.debug(
                f"Offer needs review: product={product}, "
                f"match_confidence={match_confidence:.2f}"
            )
            any_needs_review = True
            continue

        from sqlalchemy import and_, select
        existing_result = await session.execute(
            select(Offer).where(
                and_(
                    Offer.product_id == product.id,
                    Offer.supplier_id == supplier_id,
                    Offer.is_current == True,  # noqa: E712
                )
            )
        )
        existing_offers = existing_result.scalars().all()

        new_price = Decimal(str(parsed_offer.price))

        if skip_unchanged and existing_offers:
            current_price = existing_offers[0].price
            if current_price == new_price:
                logger.debug(f"Skipping unchanged price {new_price}")
                any_success = True
                skipped_unchanged += 1
                continue

        for old_offer in existing_offers:
            old_offer.is_current = False

        offer = Offer(
            supplier_id=supplier_id,
            product_id=product.id,
            raw_message_id=message.id,
            price=new_price,
            currency=parsed_offer.currency,
            detected_confidence=match_confidence,
            is_current=True,
        )
        session.add(offer)
        await session.flush()

        history_entry = PriceHistory(
            offer_id=offer.id,
            supplier_id=supplier_id,
            product_id=product.id,
            price=new_price,
            currency=parsed_offer.currency,
        )
        session.add(history_entry)

        offers_created += 1
        any_success = True
        logger.info(
            f"Created offer: {parsed_offer.model} {parsed_offer.memory} "
            f"@ {parsed_offer.price} {parsed_offer.currency}"
        )

    # Step 5: Final status
    if any_success:
        message.parse_status = "parsed"
        message.is_processed = True
        status = "parsed"
    elif any_needs_review:
        message.parse_status = "needs_review"
        message.parse_error = "Low confidence or no valid price"
        message.is_processed = True
        status = "needs_review"
    else:
        message.parse_status = "failed"
        message.parse_error = "Failed to create any offers"
        message.is_processed = True
        status = "failed"

    await session.flush()
    return status, skipped_unchanged, used_llm, False
