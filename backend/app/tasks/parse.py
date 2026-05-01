"""Parsing tasks: process raw messages into structured offers."""
import asyncio
import logging
from decimal import Decimal

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Размер батча — сколько сообщений за один запуск
PARSE_BATCH_SIZE = 50

# Макс LLM-запросов за один запуск задачи (0 = без ограничений)
LLM_MAX_PER_RUN = 50


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
    max_retries=0,  # не ретрайтить — следующий запуск beat через 60с
    soft_time_limit=3600,
    time_limit=3660,
)
def parse_pending_messages(self):
    """
    Periodic task: parse pending raw messages.
    LLM вызовы последовательные, макс LLM_MAX_PER_RUN штук за запуск.
    """
    try:
        result = _run_async(_parse_pending_messages_async())
        return result
    except Exception as exc:
        logger.error(f"Parse task failed: {exc}")
        raise


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
    """Parse pending raw messages.

    Regex-проход для всех, LLM последовательно для первых LLM_MAX_PER_RUN сообщений.
    Оставшиеся необработанные LLM-сообщения остаются pending — следующий запуск их возьмёт.
    """
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source
    from app.parser.llm_parser import parse_with_llm
    from app.parser.regex_parser import is_obviously_not_price_message, parse_message
    from app.parser.channel_strategy import preprocess_by_strategy
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
            .limit(PARSE_BATCH_SIZE)
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

        # ------------------------------------------------------------------ #
        # Шаг 1: Regex pre-pass — быстрый прогон всех сообщений               #
        # ------------------------------------------------------------------ #
        regex_results: dict[int, list] = {}
        llm_needed: list[tuple] = []  # (msg, preprocessed_text)

        for msg in messages:
            source = sources_map.get(msg.source_id)
            parsing_strategy = source.parsing_strategy if source else "auto"
            line_format = source.line_format if source else None
            text = msg.message_text

            if is_obviously_not_price_message(text):
                msg.parse_status = "failed"
                msg.parse_error = "Not a price message (pre-filter)"
                msg.is_processed = True
                stats["system_skipped"] += 1
                stats["processed"] += 1
                regex_results[msg.id] = []
                continue

            preprocessed = preprocess_by_strategy(text, parsing_strategy, line_format)

            if parsing_strategy in ("auto", "regex", "pipe", "table"):
                parse_result = parse_message(preprocessed)
                offers = parse_result.offers
            else:
                offers = []

            needs_llm = (
                parsing_strategy in ("auto", "llm")
                and (
                    not offers
                    or all(o.confidence < settings.parser_confidence_threshold for o in offers)
                )
            )

            if needs_llm and len(llm_needed) < LLM_MAX_PER_RUN:
                llm_needed.append((msg, preprocessed))
            else:
                regex_results[msg.id] = offers

        # ------------------------------------------------------------------ #
        # Шаг 2: LLM последовательно для первых LLM_MAX_PER_RUN              #
        # ------------------------------------------------------------------ #
        llm_results: dict[int, list] = {}
        if llm_needed:
            logger.info(f"LLM sequential: {len(llm_needed)} messages (max {LLM_MAX_PER_RUN})")
            for msg, text in llm_needed:
                try:
                    offers = await parse_with_llm(text)
                    llm_results[msg.id] = offers
                    stats["llm_calls"] += 1
                except Exception as e:
                    logger.error(f"LLM failed for msg {msg.id}: {e}")
                    llm_results[msg.id] = []

        # ------------------------------------------------------------------ #
        # Шаг 3: Сохранение результатов в БД                                 #
        # ------------------------------------------------------------------ #
        for msg in messages:
            if msg.parse_status in ("failed",) and msg.is_processed:
                continue

            source = sources_map.get(msg.source_id)
            supplier_id = source.supplier_id if source else None

            offers = llm_results.get(msg.id) or regex_results.get(msg.id, [])

            try:
                status, skipped = await _save_offers(
                    session=session,
                    message=msg,
                    parsed_offers=offers,
                    supplier_id=supplier_id,
                    confidence_threshold=settings.parser_confidence_threshold,
                    skip_unchanged=settings.skip_unchanged_prices,
                )
                stats["processed"] += 1
                stats["skipped_unchanged"] += skipped
                if status == "parsed":
                    stats["parsed"] += 1
                elif status == "needs_review":
                    stats["needs_review"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"Error saving message {msg.id}: {e}")
                msg.parse_status = "failed"
                msg.parse_error = str(e)[:1000]
                msg.is_processed = True
                stats["processed"] += 1
                stats["failed"] += 1

        await session.commit()

    logger.info(f"Parsing complete: {stats}")
    return stats


async def _save_offers(
    session,
    message,
    parsed_offers: list,
    supplier_id: int | None,
    confidence_threshold: float,
    skip_unchanged: bool = True,
) -> tuple[str, int]:
    """Save offers from one message. Returns (status, skipped_count)."""
    from app.models.offer import Offer
    from app.models.price_history import PriceHistory
    from app.parser.normalizer import normalize_and_match

    if not parsed_offers:
        message.parse_status = "failed"
        message.parse_error = "No offers could be extracted from the message"
        message.is_processed = True
        return "failed", 0

    any_success = False
    any_needs_review = False
    skipped_unchanged = 0

    for parsed_offer in parsed_offers:
        if not supplier_id:
            any_needs_review = True
            continue

        if parsed_offer.price is None or parsed_offer.price <= 0:
            any_needs_review = True
            continue

        product, match_confidence = await normalize_and_match(parsed_offer, session)

        if product is None or match_confidence < confidence_threshold:
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
            if existing_offers[0].price == new_price:
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
        any_success = True
        logger.info(
            f"Created offer: {parsed_offer.model} {parsed_offer.memory} "
            f"@ {parsed_offer.price} {parsed_offer.currency}"
        )

    if any_success:
        message.parse_status = "parsed"
        message.is_processed = True
        return "parsed", skipped_unchanged
    elif any_needs_review:
        message.parse_status = "needs_review"
        message.parse_error = "Low confidence or no valid price"
        message.is_processed = True
        return "needs_review", 0
    else:
        message.parse_status = "failed"
        message.parse_error = "Failed to create any offers"
        message.is_processed = True
        return "failed", 0


async def _parse_single_message_async(message_id: int) -> dict:
    from sqlalchemy import select

    from app.config import settings
    from app.database import get_isolated_session
    from app.models.raw_message import RawMessage
    from app.models.source import Source
    from app.parser.llm_parser import parse_with_llm
    from app.parser.regex_parser import is_obviously_not_price_message, parse_message
    from app.parser.channel_strategy import preprocess_by_strategy
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
        line_format = source.line_format if source else None

        if source and not source.supplier_id:
            await get_or_create_supplier_for_source(source, session)
            await session.flush()

        supplier_id = source.supplier_id if source else None
        text = message.message_text

        if is_obviously_not_price_message(text):
            message.parse_status = "failed"
            message.parse_error = "Not a price message (pre-filter)"
            message.is_processed = True
            await session.commit()
            return {"message_id": message_id, "status": "failed"}

        preprocessed = preprocess_by_strategy(text, parsing_strategy, line_format)
        offers = []

        if parsing_strategy in ("auto", "regex", "pipe", "table"):
            parse_result = parse_message(preprocessed)
            offers = parse_result.offers

        needs_llm = (
            parsing_strategy in ("auto", "llm")
            and (not offers or all(o.confidence < settings.parser_confidence_threshold for o in offers))
        )
        if needs_llm:
            llm_offers = await parse_with_llm(preprocessed)
            if llm_offers:
                offers = llm_offers

        status, _ = await _save_offers(
            session=session,
            message=message,
            parsed_offers=offers,
            supplier_id=supplier_id,
            confidence_threshold=settings.parser_confidence_threshold,
            skip_unchanged=settings.skip_unchanged_prices,
        )
        await session.commit()
        return {"message_id": message_id, "status": status}
