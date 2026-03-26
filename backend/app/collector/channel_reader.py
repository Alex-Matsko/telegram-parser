import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import (
    InputPeerEmpty,
    InputPeerUser,
    Message,
    PeerUser,
    User,
)

from app.config import settings
from app.models.raw_message import RawMessage
from app.models.source import Source

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _find_user_in_dialogs(
    client: TelegramClient, user_id: int
) -> Optional[InputPeerUser]:
    """
    Scan recent dialogs to find a User with the given user_id and
    return an InputPeerUser (which carries the required access_hash).

    Telethon cannot open a user dialog using only the numeric user_id —
    it also needs the access_hash that Telegram hands out when you first
    interact with a user.  The safest way to get it without a cached
    session entry is to iterate GetDialogsRequest until we find the peer.
    """
    offset_date = 0
    offset_id = 0
    offset_peer = InputPeerEmpty()
    chunk = 100

    while True:
        result = await client(GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=chunk,
            hash=0,
        ))

        if not result.dialogs:
            break

        for user in result.users:
            if isinstance(user, User) and user.id == user_id:
                logger.info(
                    f"[user-resolve] Found user id={user.id} "
                    f"username={getattr(user, 'username', None)} "
                    f"in dialogs"
                )
                return InputPeerUser(
                    user_id=user.id,
                    access_hash=user.access_hash,
                )

        if len(result.dialogs) < chunk:
            break

        last_msg = result.messages[-1]
        offset_id = last_msg.id if hasattr(last_msg, 'id') else 0
        offset_date = last_msg.date if hasattr(last_msg, 'date') else 0
        offset_peer = result.dialogs[-1].peer

    return None


async def _resolve_entity(client: TelegramClient, source: Source):
    """
    Resolve a Telethon entity for any source type:
    - channel / group : telegram_id is negative (e.g. -1002674030582)
    - user            : telegram_id is a positive user_id (e.g. 5701246948)

    For 'user' sources we first try client.get_input_entity() (works if the
    session already has the user cached from a previous interaction), then
    fall back to scanning dialogs to retrieve the access_hash.
    """
    if source.type != "user":
        return await client.get_entity(source.telegram_id)

    user_id = source.telegram_id

    # Fast path — session cache already has this user
    try:
        entity = await client.get_input_entity(PeerUser(user_id))
        logger.info(f"[user-resolve] Found user id={user_id} in session cache")
        return entity
    except ValueError:
        pass

    # Slow path — scan dialogs
    logger.info(
        f"[user-resolve] user_id={user_id} not in session cache, "
        f"scanning dialogs ..."
    )
    entity = await _find_user_in_dialogs(client, user_id)
    if entity is not None:
        return entity

    raise ValueError(
        f"Cannot resolve user_id={user_id}: user not found in session cache "
        f"or recent dialogs. Make sure you have an open conversation with this "
        f"user in the Telegram account whose session string is configured."
    )


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 200,
) -> int:
    """
    Read new messages from a Telegram channel, group, or user dialog.

    - Incremental run: newest-first, stop at last_message_id boundary.
    - First run: use offset_date=cutoff, newest-first, up to limit messages.
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
        f"type={source.type} | telegram_id={source.telegram_id} | "
        f"last_message_id={source.last_message_id} | "
        f"cutoff={cutoff_date.strftime('%Y-%m-%d %H:%M')} UTC "
        f"(history_days={history_days}) | limit={limit}"
    )

    try:
        entity = await _resolve_entity(client, source)
        entity_type = type(entity).__name__
        entity_id = getattr(entity, 'user_id', None) or getattr(entity, 'id', '?')
        entity_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(entity_id))
        logger.info(
            f"[{source.source_name}] ✔ Entity resolved: "
            f"type={entity_type} | id={entity_id} | title={entity_title}"
        )

        messages: list[Message] = []

        if is_first_run:
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
                    continue
                messages.append(message)
            messages.reverse()

        else:
            min_id = source.last_message_id
            async for message in client.iter_messages(
                entity,
                limit=limit,
                reverse=False,
            ):
                if message.id <= min_id:
                    logger.debug(
                        f"[{source.source_name}] ⏹ Reached boundary id={message.id} "
                        f"(≤ last_message_id={min_id}), stopping"
                    )
                    break
                if not message.text:
                    skipped_empty += 1
                    continue
                msg_date = _ensure_utc(message.date) if message.date else None
                if msg_date and msg_date < cutoff_date:
                    skipped_old += 1
                    continue
                messages.append(message)
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
