import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.types import Message

from app.models.raw_message import RawMessage
from app.models.source import Source

logger = logging.getLogger(__name__)

HISTORY_DAYS = 7  # how far back to look (applies to EVERY run, not just first)


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 500,
) -> int:
    """
    Read new messages from a Telegram channel or group.

    - First run (last_message_id is None): fetches messages from the last
      HISTORY_DAYS days only (hard cutoff enforced both via offset_date and
      in-loop date filter).
    - Subsequent runs: fetches only messages newer than last_message_id,
      but still discards anything older than HISTORY_DAYS as a safety net
      (prevents replaying old backlog if last_message_id is stale/reset).

    Returns the number of new messages saved.
    """
    saved_count = 0
    skipped_old = 0

    # Hard cutoff — always enforced, on every run
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)

    try:
        entity = await client.get_entity(source.telegram_id)

        is_first_run = source.last_message_id is None
        min_id = source.last_message_id or 0

        # On first run pass offset_date so Telethon starts near the cutoff
        # and doesn't stream thousands of old messages over the wire.
        # On incremental runs min_id is already the right lower bound.
        offset_date = cutoff_date if is_first_run else None

        messages: list[Message] = []
        async for message in client.iter_messages(
            entity,
            limit=limit,
            min_id=min_id,
            offset_date=offset_date,
            reverse=True,
        ):
            if not message.text:
                continue

            # Hard date guard — drop anything older than cutoff regardless
            # of how Telethon interpreted offset_date or min_id.
            if message.date and message.date < cutoff_date:
                skipped_old += 1
                continue

            messages.append(message)

        if skipped_old:
            logger.info(
                f"[{source.source_name}] Skipped {skipped_old} messages older "
                f"than {HISTORY_DAYS} days (cutoff: {cutoff_date.date()})"
            )

        if not messages:
            logger.info(f"No new messages for source {source.source_name} (id={source.id})")
            return 0

        last_msg_id = source.last_message_id or 0
        for msg in messages:
            sender_name = await _get_sender_name(msg)
            raw_payload = {
                "message_id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "forward_from": str(msg.forward) if msg.forward else None,
                "reply_to": msg.reply_to_msg_id if msg.reply_to else None,
            }

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

            if msg.id > last_msg_id:
                last_msg_id = msg.id

        source.last_message_id = last_msg_id
        source.last_read_at = datetime.now(timezone.utc)
        source.error_count = 0
        source.last_error = None
        await session.flush()

        logger.info(
            f"[{'first-run' if is_first_run else 'incremental'}] "
            f"Saved {saved_count} new messages from {source.source_name} (id={source.id})"
        )

    except Exception as e:
        logger.error(f"Error reading source {source.source_name} (id={source.id}): {e}")
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
                return " \".join(parts).strip() or None
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
