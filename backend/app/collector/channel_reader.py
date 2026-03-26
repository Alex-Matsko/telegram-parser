import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.types import Message

from app.config import settings
from app.models.raw_message import RawMessage
from app.models.source import Source

logger = logging.getLogger(__name__)


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 500,
) -> int:
    """
    Read new messages from a Telegram channel or group.

    - First run (last_message_id is None): fetches messages from the last
      settings.collector_history_days days only (hard cutoff enforced both
      via offset_date and in-loop date filter).
    - Subsequent runs: fetches only messages newer than last_message_id,
      but still discards anything older than collector_history_days as a
      safety net (prevents replaying old backlog if last_message_id is reset).

    Returns the number of new messages saved.
    """
    saved_count = 0
    skipped_old = 0
    skipped_empty = 0

    history_days = settings.collector_history_days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=history_days)
    is_first_run = source.last_message_id is None
    run_type = "first-run" if is_first_run else "incremental"

    logger.info(
        f"[{source.source_name}] ▶ START {run_type} | "
        f"telegram_id={source.telegram_id} | "
        f"last_message_id={source.last_message_id} | "
        f"cutoff={cutoff_date.date()} (history_days={history_days}) | "
        f"limit={limit}"
    )

    try:
        logger.debug(f"[{source.source_name}] Resolving entity for telegram_id={source.telegram_id} ...")
        entity = await client.get_entity(source.telegram_id)
        logger.info(
            f"[{source.source_name}] ✔ Entity resolved: "
            f"type={type(entity).__name__} | id={getattr(entity, 'id', '?')} | "
            f"title={getattr(entity, 'title', getattr(entity, 'username', '?'))}"
        )

        min_id = source.last_message_id or 0
        offset_date = cutoff_date if is_first_run else None

        logger.debug(
            f"[{source.source_name}] Starting iter_messages: "
            f"min_id={min_id} | offset_date={offset_date} | reverse=True"
        )

        messages: list[Message] = []
        async for message in client.iter_messages(
            entity,
            limit=limit,
            min_id=min_id,
            offset_date=offset_date,
            reverse=True,
        ):
            if not message.text:
                skipped_empty += 1
                continue

            if message.date and message.date < cutoff_date:
                skipped_old += 1
                logger.debug(
                    f"[{source.source_name}] ⏭ Skipped old message "
                    f"id={message.id} date={message.date.date()}"
                )
                continue

            messages.append(message)
            logger.debug(
                f"[{source.source_name}] + Queued message id={message.id} "
                f"date={message.date} len={len(message.text)} chars"
            )

        logger.info(
            f"[{source.source_name}] Fetch complete: "
            f"queued={len(messages)} | skipped_old={skipped_old} | skipped_empty={skipped_empty}"
        )

        if not messages:
            logger.info(
                f"[{source.source_name}] ✔ No new messages — source is up to date "
                f"(id={source.id})"
            )
            return 0

        last_msg_id = source.last_message_id or 0
        for idx, msg in enumerate(messages):
            sender_name = await _get_sender_name(msg)
            raw_payload = {
                "message_id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "forward_from": str(msg.forward) if msg.forward else None,
                "reply_to": msg.reply_to_msg_id if msg.reply_to else None,
            }

            logger.debug(
                f"[{source.source_name}] Saving [{idx + 1}/{len(messages)}] "
                f"msg_id={msg.id} | sender={sender_name} | "
                f"date={msg.date} | text_preview={msg.text[:80]!r}"
            )

            stmt = pg_insert(RawMessage).values(
                source_id=source.id,
                telegram_message_id=msg.id,
                message_text=msg.text,
                message_date=msg.date or datetime.now(timezone.utc),
                sender_name=sender_name,
                raw_payload=raw_payload,
                is_processed=False,
                parse_status="pending",
            ).on_conflict_do_nothing(
                constraint="uq_source_message",
            )
            result = await session.execute(stmt)
            if result.rowcount > 0:
                saved_count += 1
                logger.debug(f"[{source.source_name}] ✔ Saved msg_id={msg.id}")
            else:
                logger.debug(f"[{source.source_name}] ⚠ Duplicate skipped msg_id={msg.id}")

            if msg.id > last_msg_id:
                last_msg_id = msg.id

        source.last_message_id = last_msg_id
        source.last_read_at = datetime.now(timezone.utc)
        source.error_count = 0
        source.last_error = None
        await session.flush()

        logger.info(
            f"[{source.source_name}] ✅ DONE [{run_type}] | "
            f"saved={saved_count} | duplicates={len(messages) - saved_count} | "
            f"new last_message_id={last_msg_id}"
        )

    except Exception as e:
        logger.error(
            f"[{source.source_name}] ❌ FAILED (id={source.id}) | "
            f"error={type(e).__name__}: {e}",
            exc_info=True,
        )
        source.error_count = (source.error_count or 0) + 1
        source.last_error = str(e)[:1000]
        await session.flush()
        raise

    return saved_count


async def _get_sender_name(message: Message) -> Optional[str]:
    try:
        if message.sender:
            sender = message.sender
            if hasattr(sender, "first_name"):
                parts = [sender.first_name or ""]
                if hasattr(sender, "last_name") and sender.last_name:
                    parts.append(sender.last_name)
                return " ".join(parts).strip() or None
            if hasattr(sender, "title"):
                return sender.title
    except Exception:
        pass
    return None


async def get_active_sources(session: AsyncSession) -> list[Source]:
    result = await session.execute(
        select(Source).where(Source.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())
