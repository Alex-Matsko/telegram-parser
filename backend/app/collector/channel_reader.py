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


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC. Telethon usually returns UTC-aware,
    but some builds return naive UTC datetimes — this handles both cases."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 200,
) -> int:
    """
    Read new messages from a Telegram channel or group.

    Strategy:
    - Incremental run (last_message_id is set):
        iter_messages newest-first (reverse=False), stop as soon as we hit
        a message id <= last_message_id OR date < cutoff. This way `limit`
        counts only messages we haven’t seen yet, not the whole history.
    - First run (last_message_id is None):
        Use offset_date=cutoff so Telethon starts near the cutoff boundary,
        then collect up to `limit` messages going newest-first and keep only
        those within the cutoff window.

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
        f"cutoff={cutoff_date.strftime('%Y-%m-%d %H:%M')} UTC "
        f"(history_days={history_days}) | limit={limit}"
    )

    try:
        logger.debug(
            f"[{source.source_name}] Resolving entity for telegram_id={source.telegram_id} ..."
        )
        entity = await client.get_entity(source.telegram_id)
        logger.info(
            f"[{source.source_name}] ✔ Entity resolved: "
            f"type={type(entity).__name__} | id={getattr(entity, 'id', '?')} | "
            f"title={getattr(entity, 'title', getattr(entity, 'username', '?'))}"
        )

        messages: list[Message] = []

        if is_first_run:
            # --- FIRST RUN: newest-first from offset_date ---
            # offset_date tells Telethon to start at messages around that date.
            # We iterate newest-first (reverse=False default) and stop when
            # we go past the cutoff.
            logger.debug(
                f"[{source.source_name}] First-run iter: offset_date={cutoff_date} "
                f"reverse=False limit={limit}"
            )
            async for message in client.iter_messages(
                entity,
                limit=limit,
                offset_date=cutoff_date,
                reverse=False,
            ):
                if not message.text:
                    skipped_empty += 1
                    continue
                msg_date = _ensure_utc(message.date) if message.date else None
                if msg_date and msg_date < cutoff_date:
                    skipped_old += 1
                    logger.debug(
                        f"[{source.source_name}] ⏭ Skipped old id={message.id} "
                        f"date={msg_date}"
                    )
                    continue
                messages.append(message)
                logger.debug(
                    f"[{source.source_name}] + Queued id={message.id} "
                    f"date={msg_date} len={len(message.text)}"
                )

            # Restore chronological order for saving
            messages.reverse()

        else:
            # --- INCREMENTAL RUN: newest-first, stop at known boundary ---
            # Do NOT use reverse=True — it counts limit from the very beginning
            # of history. Instead go newest-first and break early.
            min_id = source.last_message_id  # exclusive lower bound
            logger.debug(
                f"[{source.source_name}] Incremental iter: min_id={min_id} "
                f"reverse=False limit={limit}"
            )
            async for message in client.iter_messages(
                entity,
                limit=limit,
                reverse=False,
            ):
                # Stop as soon as we reach already-seen messages
                if message.id <= min_id:
                    logger.debug(
                        f"[{source.source_name}] ⏹ Reached known boundary at "
                        f"id={message.id} (≤ last_message_id={min_id}), stopping"
                    )
                    break

                if not message.text:
                    skipped_empty += 1
                    continue

                msg_date = _ensure_utc(message.date) if message.date else None
                if msg_date and msg_date < cutoff_date:
                    skipped_old += 1
                    logger.debug(
                        f"[{source.source_name}] ⏭ Skipped old id={message.id} "
                        f"date={msg_date}"
                    )
                    continue

                messages.append(message)
                logger.debug(
                    f"[{source.source_name}] + Queued id={message.id} "
                    f"date={msg_date} len={len(message.text)}"
                )

            # Restore chronological order for saving
            messages.reverse()

        logger.info(
            f"[{source.source_name}] Fetch complete: "
            f"queued={len(messages)} | skipped_old={skipped_old} | "
            f"skipped_empty={skipped_empty}"
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
            msg_date = _ensure_utc(msg.date) if msg.date else datetime.now(timezone.utc)
            raw_payload = {
                "message_id": msg.id,
                "date": msg_date.isoformat(),
                "forward_from": str(msg.forward) if msg.forward else None,
                "reply_to": msg.reply_to_msg_id if msg.reply_to else None,
            }

            logger.debug(
                f"[{source.source_name}] Saving [{idx + 1}/{len(messages)}] "
                f"msg_id={msg.id} | sender={sender_name} | "
                f"date={msg_date} | preview={msg.text[:80]!r}"
            )

            stmt = pg_insert(RawMessage).values(
                source_id=source.id,
                telegram_message_id=msg.id,
                message_text=msg.text,
                message_date=msg_date,
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
                logger.debug(
                    f"[{source.source_name}] ⚠ Duplicate skipped msg_id={msg.id}"
                )

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
