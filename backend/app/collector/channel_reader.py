import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.types import Message

from app.models.raw_message import RawMessage
from app.models.source import Source

logger = logging.getLogger(__name__)


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 100,
) -> int:
    """
    Read new messages from a Telegram channel or group.

    Returns the number of new messages saved.
    """
    saved_count = 0
    try:
        entity = await client.get_entity(source.telegram_id)
        min_id = source.last_message_id or 0

        messages: list[Message] = []
        async for message in client.iter_messages(
            entity,
            limit=limit,
            min_id=min_id,
            reverse=True,
        ):
            if message.text:
                messages.append(message)

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

        # Update source tracking
        source.last_message_id = last_msg_id
        source.last_read_at = datetime.now(timezone.utc)
        source.error_count = 0
        source.last_error = None
        await session.flush()

        logger.info(
            f"Saved {saved_count} new messages from source "
            f"{source.source_name} (id={source.id})"
        )

    except Exception as e:
        logger.error(f"Error reading source {source.source_name} (id={source.id}): {e}")
        source.error_count = (source.error_count or 0) + 1
        source.last_error = str(e)[:1000]
        await session.flush()
        raise

    return saved_count


async def _get_sender_name(message: Message) -> Optional[str]:
    """Extract sender name from a Telegram message."""
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
    """Get all active sources that need to be polled."""
    result = await session.execute(
        select(Source).where(Source.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())
