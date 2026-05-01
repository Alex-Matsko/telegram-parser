import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.custom import Message
from telethon.tl.types import (
    KeyboardButtonCallback,
    KeyboardButtonRow,
    ReplyInlineMarkup,
    ReplyKeyboardMarkup,
)

from app.models.bot_scenario import BotScenario
from app.models.raw_message import RawMessage
from app.models.source import Source

logger = logging.getLogger(__name__)


class BotInteractionResult:
    def __init__(self) -> None:
        self.success: bool = True
        self.steps_executed: int = 0
        self.collected_messages: list[str] = []
        self.errors: list[str] = []


def _unique_message_id() -> int:
    return uuid.uuid4().int & 0x7FFFFFFF


async def _resolve_entity(client: TelegramClient, source: Source):
    """
    Резолвит entity бота с fallback:
    1. По telegram_id (числовой ID)
    2. По username из source_name (если ID не найден в кэше сессии)
    """
    # Попытка 1: по числовому ID
    try:
        return await client.get_entity(source.telegram_id)
    except ValueError:
        pass

    # Попытка 2: по username из source_name (может быть '@botname' или 'botname')
    username = source.source_name
    if username and not username.startswith("@"):
        username = f"@{username}"
    if username:
        try:
            entity = await client.get_entity(username)
            logger.info(
                f"[BOT:{source.source_name}] ✔ Entity resolved via username fallback: "
                f"type={type(entity).__name__} | id={getattr(entity, 'id', '?')}"
            )
            return entity
        except ValueError:
            pass

    # Ничего не сработало
    raise ValueError(
        f"Could not find the input entity for telegram_id={source.telegram_id} "
        f"and username='{source.source_name}'. "
        f"Make sure the account has previously interacted with this bot."
    )


async def execute_bot_scenario(
    client: TelegramClient,
    source: Source,
    scenario: BotScenario,
    session: AsyncSession,
) -> BotInteractionResult:
    """
    Execute a bot interaction scenario step by step.
    Collects response messages and saves them as raw messages.
    """
    result = BotInteractionResult()
    steps = scenario.steps_json
    total_steps = len(steps) if steps else 0

    logger.info(
        f"[BOT:{source.source_name}] ▶ START scenario='{scenario.scenario_name}' | "
        f"source_id={source.id} | telegram_id={source.telegram_id} | "
        f"total_steps={total_steps}"
    )

    if not steps:
        msg = "Scenario has no steps"
        logger.error(f"[BOT:{source.source_name}] ❌ {msg}")
        result.success = False
        result.errors.append(msg)
        return result

    try:
        logger.debug(
            f"[BOT:{source.source_name}] Resolving entity telegram_id={source.telegram_id} ..."
        )
        entity = await _resolve_entity(client, source)
        logger.info(
            f"[BOT:{source.source_name}] ✔ Entity resolved: "
            f"type={type(entity).__name__} | id={getattr(entity, 'id', '?')}"
        )
    except Exception as e:
        msg = f"Failed to get bot entity: {e}"
        logger.error(
            f"[BOT:{source.source_name}] ❌ {msg}",
            exc_info=True,
        )
        result.success = False
        result.errors.append(msg)
        return result

    last_bot_message: Optional[Message] = None

    for i, step in enumerate(steps):
        action = step.get("action", "")
        value = step.get("value", "")
        wait_sec = step.get("wait_sec", 2)
        step_label = f"Step [{i + 1}/{total_steps}] action='{action}'"

        logger.info(
            f"[BOT:{source.source_name}] {step_label} "
            f"value={value!r} wait_sec={wait_sec}"
        )

        try:
            if action in ("send_command", "send_text"):
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} → Sending message: {value!r}"
                )
                await client.send_message(entity, value)
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} ⏳ Waiting {wait_sec}s for response ..."
                )
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)
                if last_bot_message:
                    logger.debug(
                        f"[BOT:{source.source_name}] {step_label} ✔ Bot replied: "
                        f"msg_id={last_bot_message.id} | "
                        f"preview={last_bot_message.text[:80]!r}"
                    )
                else:
                    logger.warning(
                        f"[BOT:{source.source_name}] {step_label} ⚠ No bot reply found after waiting"
                    )

            elif action == "click_inline":
                if last_bot_message is None:
                    logger.debug(
                        f"[BOT:{source.source_name}] {step_label} Fetching last bot message ..."
                    )
                    last_bot_message = await _get_last_bot_message(client, entity)
                if last_bot_message is None:
                    err = f"{step_label}: No message with inline buttons found"
                    logger.warning(f"[BOT:{source.source_name}] ⚠ {err}")
                    result.errors.append(err)
                    continue
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} → Clicking inline button: {value!r}"
                )
                clicked = await _click_inline_button(client, last_bot_message, value)
                if not clicked:
                    err = f"{step_label}: Inline button '{value}' not found"
                    logger.warning(f"[BOT:{source.source_name}] ⚠ {err}")
                    result.errors.append(err)
                    continue
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} ✔ Clicked. Waiting {wait_sec}s ..."
                )
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)

            elif action == "click_reply":
                if last_bot_message is None:
                    last_bot_message = await _get_last_bot_message(client, entity)
                if last_bot_message is None:
                    err = f"{step_label}: No message with reply keyboard found"
                    logger.warning(f"[BOT:{source.source_name}] ⚠ {err}")
                    result.errors.append(err)
                    continue
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} → Clicking reply button: {value!r}"
                )
                clicked = await _click_reply_button(client, entity, last_bot_message, value)
                if not clicked:
                    err = f"{step_label}: Reply button '{value}' not found"
                    logger.warning(f"[BOT:{source.source_name}] ⚠ {err}")
                    result.errors.append(err)
                    continue
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} ✔ Clicked. Waiting {wait_sec}s ..."
                )
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)

            elif action == "collect_response":
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} Collecting recent messages (limit=10) ..."
                )
                messages = await _collect_recent_messages(client, entity, limit=10)
                before = len(result.collected_messages)
                for msg in messages:
                    if msg.text:
                        result.collected_messages.append(msg.text)
                after = len(result.collected_messages)
                logger.info(
                    f"[BOT:{source.source_name}] {step_label} ✔ Collected {after - before} messages "
                    f"(total so far: {after})"
                )

            elif action == "wait":
                logger.debug(
                    f"[BOT:{source.source_name}] {step_label} ⏳ Explicit wait {wait_sec}s"
                )
                await asyncio.sleep(wait_sec)

            else:
                err = f"{step_label}: Unknown action '{action}'"
                logger.warning(f"[BOT:{source.source_name}] ⚠ {err}")
                result.errors.append(err)
                continue

            result.steps_executed += 1
            logger.debug(
                f"[BOT:{source.source_name}] {step_label} ✅ Complete"
            )

        except Exception as e:
            err = f"{step_label} ({action}): {e}"
            result.errors.append(err)
            logger.error(
                f"[BOT:{source.source_name}] ❌ {err}",
                exc_info=True,
            )

    # Save collected messages as raw messages
    saved = 0
    logger.info(
        f"[BOT:{source.source_name}] Saving {len(result.collected_messages)} "
        f"collected messages to DB ..."
    )
    for msg_text in result.collected_messages:
        stmt = pg_insert(RawMessage).values(
            source_id=source.id,
            telegram_message_id=_unique_message_id(),
            message_text=msg_text,
            message_date=datetime.now(timezone.utc),
            sender_name=scenario.bot_name,
            raw_payload={"scenario_id": scenario.id, "scenario_name": scenario.scenario_name},
            is_processed=False,
            parse_status="pending",
        ).on_conflict_do_nothing(constraint="uq_source_message")
        await session.execute(stmt)
        saved += 1

    source.last_read_at = datetime.now(timezone.utc)
    await session.flush()

    if result.errors:
        result.success = len(result.collected_messages) > 0
        logger.warning(
            f"[BOT:{source.source_name}] Scenario finished WITH ERRORS: "
            f"{result.errors}"
        )
    else:
        result.success = True

    logger.info(
        f"[BOT:{source.source_name}] ✅ DONE scenario='{scenario.scenario_name}' | "
        f"steps_executed={result.steps_executed}/{total_steps} | "
        f"messages_collected={len(result.collected_messages)} | "
        f"saved_to_db={saved} | "
        f"errors={len(result.errors)}"
    )
    return result


async def _get_last_bot_message(
    client: TelegramClient, entity: object, limit: int = 5
) -> Optional[Message]:
    async for msg in client.iter_messages(entity, limit=limit):
        if msg.out is False and msg.text:
            return msg
    return None


async def _click_inline_button(
    client: TelegramClient, message: Message, button_text: str
) -> bool:
    if not message.reply_markup or not isinstance(message.reply_markup, ReplyInlineMarkup):
        return False

    for row in message.reply_markup.rows:
        if not isinstance(row, KeyboardButtonRow):
            continue
        for button in row.buttons:
            if hasattr(button, "text") and button_text.lower() in button.text.lower():
                if isinstance(button, KeyboardButtonCallback):
                    await message.click(data=button.data)
                else:
                    await message.click(text=button.text)
                return True
    return False


async def _click_reply_button(
    client: TelegramClient,
    entity: object,
    message: Message,
    button_text: str,
) -> bool:
    if not message.reply_markup or not isinstance(message.reply_markup, ReplyKeyboardMarkup):
        return False

    for row in message.reply_markup.rows:
        if not isinstance(row, KeyboardButtonRow):
            continue
        for button in row.buttons:
            if hasattr(button, "text") and button_text.lower() in button.text.lower():
                await client.send_message(entity, button.text)
                return True
    return False


async def _collect_recent_messages(
    client: TelegramClient, entity: object, limit: int = 10
) -> list[Message]:
    messages = []
    async for msg in client.iter_messages(entity, limit=limit):
        if msg.out is False and msg.text:
            messages.append(msg)
    messages.reverse()
    return messages
