import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
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
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _resolve_bot(client: TelegramClient, source: Source):
    """
    Resolve a bot entity.

    Bots don't appear in contacts.Search or dialog scans.
    The only reliable method is get_entity('@username').

    Strategy:
    1. Session cache via telegram_id (works on 2nd+ run)
    2. Username lookup via source_name (strips leading @)
    3. Username lookup via stored username field if present
    """
    # 1. Session cache
    try:
        entity = await client.get_input_entity(PeerUser(source.telegram_id))
        logger.info(f"[bot-resolve] id={source.telegram_id} found in session cache")
        return entity
    except (ValueError, KeyError):
        pass

    # 2. Try source_name as username (most common case: name = @t_go_price_bot)
    username = source.source_name.lstrip("@").strip()
    try:
        entity = await client.get_entity(f"@{username}")
        logger.info(
            f"[bot-resolve] id={source.telegram_id} resolved via @{username}"
        )
        return entity
    except Exception as e:
        logger.debug(f"[bot-resolve] get_entity(@{username}) failed: {e}")

    # 3. Try username stored in source.username field if model has it
    stored_username = getattr(source, "username", None)
    if stored_username and stored_username != username:
        try:
            uname = stored_username.lstrip("@").strip()
            entity = await client.get_entity(f"@{uname}")
            logger.info(
                f"[bot-resolve] id={source.telegram_id} resolved via stored @{uname}"
            )
            return entity
        except Exception as e:
            logger.debug(f"[bot-resolve] get_entity(@{stored_username}) failed: {e}")

    raise ValueError(
        f"Cannot resolve bot id={source.telegram_id} (source='{source.source_name}'): "
        f"not found in session cache or by username. "
        f"Make sure the source_name matches the bot's @username."
    )


async def _search_user_by_id(
    client: TelegramClient, user_id: int, source_name: str
) -> Optional[InputPeerUser]:
    # 1. Session cache
    try:
        entity = await client.get_input_entity(PeerUser(user_id))
        logger.info(f"[user-resolve] id={user_id} found in session cache")
        return entity
    except (ValueError, KeyError):
        pass

    # 2. contacts.Search by source_name
    query = source_name.lstrip("@").strip()
    try:
        result = await client(SearchRequest(q=query, limit=10))
        for user in result.users:
            if isinstance(user, User) and user.id == user_id:
                logger.info(
                    f"[user-resolve] id={user_id} found via contacts.Search "
                    f"query={query!r}"
                )
                return InputPeerUser(user_id=user.id, access_hash=user.access_hash)
    except Exception as e:
        logger.debug(f"[user-resolve] contacts.Search failed: {e}")

    # 3. Full dialog scan
    logger.info(
        f"[user-resolve] id={user_id} not found in cache/search, scanning dialogs ..."
    )
    offset_date = 0
    offset_id = 0
    offset_peer = InputPeerEmpty()
    chunk = 100
    page = 0

    while True:
        page += 1
        res = await client(GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=chunk,
            hash=0,
        ))
        if not res.dialogs:
            break
        for user in res.users:
            if isinstance(user, User) and user.id == user_id:
                logger.info(
                    f"[user-resolve] id={user_id} found in dialogs page={page}"
                )
                return InputPeerUser(user_id=user.id, access_hash=user.access_hash)
        if len(res.dialogs) < chunk:
            break
        last_msg = res.messages[-1]
        offset_id = getattr(last_msg, 'id', 0)
        offset_date = getattr(last_msg, 'date', 0)
        offset_peer = res.dialogs[-1].peer

    logger.warning(
        f"[user-resolve] id={user_id} not found after {page} dialog page(s)"
    )
    return None


async def _resolve_entity(client: TelegramClient, source: Source):
    """
    Resolve a Telegram entity for any source type:
      - channel / group  → get_entity(telegram_id)
      - user             → session cache → contacts.Search → dialog scan
      - bot              → session cache → get_entity(@username)
    """
    source_type = (source.type or "").lower()

    if source_type == "bot":
        return await _resolve_bot(client, source)

    if source_type == "user":
        entity = await _search_user_by_id(
            client, source.telegram_id, source.source_name
        )
        if entity is not None:
            return entity
        raise ValueError(
            f"Cannot resolve user_id={source.telegram_id} "
            f"(source='{source.source_name}'): not found in session cache, "
            f"contacts search, or dialog scan."
        )

    # channel / group / supergroup
    return await client.get_entity(source.telegram_id)


async def read_channel_messages(
    client: TelegramClient,
    source: Source,
    session: AsyncSession,
    limit: int = 200,
) -> int:
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
        entity_id = getattr(entity, 'user_id', None) or getattr(entity, 'id', '?')
        entity_title = (
            getattr(entity, 'title', None)
            or getattr(entity, 'username', None)
            or str(entity_id)
        )
        logger.info(
            f"[{source.source_name}] ✔ Entity resolved: "
            f"type={type(entity).__name__} | id={entity_id} | title={entity_title}"
        )

        messages: list[Message] = []

        if is_first_run:
            async for message in client.iter_messages(entity, limit=limit):
                if not message.text:
                    skipped_empty += 1
                    continue
                msg_date = _ensure_utc(message.date) if message.date else None
                if msg_date and msg_date < cutoff_date:
                    logger.debug(
                        f"[{source.source_name}] ⏹ Reached cutoff at "
                        f"msg id={message.id} date={msg_date}, stopping"
                    )
                    skipped_old += 1
                    break
                messages.append(message)
            messages.reverse()
        else:
            min_id = source.last_message_id
            async for message in client.iter_messages(entity, limit=limit):
                if message.id <= min_id:
                    logger.debug(
                        f"[{source.source_name}] ⏹ Reached boundary "
                        f"id={message.id} (≤ {min_id}), stopping"
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
                f"[{source.source_name}] ✔ No new messages — up to date "
                f"(id={source.id})"
            )
            return 0

        last_msg_id = source.last_message_id or 0
        for msg in messages:
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
            ).on_conflict_do_nothing(constraint="uq_source_message")
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
