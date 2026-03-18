import asyncio
import logging
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

    if not steps:
        result.success = False
        result.errors.append("Scenario has no steps")
        return result

    try:
        entity = await client.get_entity(source.telegram_id)
    except Exception as e:
        result.success = False
        result.errors.append(f"Failed to get bot entity: {e}")
        return result

    last_bot_message: Optional[Message] = None

    for i, step in enumerate(steps):
        action = step.get("action", "")
        value = step.get("value", "")
        wait_sec = step.get("wait_sec", 2)

        try:
            if action == "send_command" or action == "send_text":
                await client.send_message(entity, value)
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)

            elif action == "click_inline":
                if last_bot_message is None:
                    last_bot_message = await _get_last_bot_message(client, entity)
                if last_bot_message is None:
                    result.errors.append(f"Step {i}: No message with inline buttons found")
                    continue
                clicked = await _click_inline_button(client, last_bot_message, value)
                if not clicked:
                    result.errors.append(
                        f"Step {i}: Inline button '{value}' not found"
                    )
                    continue
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)

            elif action == "click_reply":
                if last_bot_message is None:
                    last_bot_message = await _get_last_bot_message(client, entity)
                if last_bot_message is None:
                    result.errors.append(f"Step {i}: No message with reply keyboard found")
                    continue
                clicked = await _click_reply_button(client, entity, last_bot_message, value)
                if not clicked:
                    result.errors.append(
                        f"Step {i}: Reply button '{value}' not found"
                    )
                    continue
                await asyncio.sleep(wait_sec)
                last_bot_message = await _get_last_bot_message(client, entity)

            elif action == "collect_response":
                messages = await _collect_recent_messages(client, entity, limit=10)
                for msg in messages:
                    if msg.text:
                        result.collected_messages.append(msg.text)

            elif action == "wait":
                await asyncio.sleep(wait_sec)

            else:
                result.errors.append(f"Step {i}: Unknown action '{action}'")
                continue

            result.steps_executed += 1

        except Exception as e:
            result.errors.append(f"Step {i} ({action}): {e}")
            logger.error(f"Bot scenario step {i} failed: {e}")

    # Save collected messages as raw messages
    saved = 0
    for msg_text in result.collected_messages:
        stmt = pg_insert(RawMessage).values(
            source_id=source.id,
            telegram_message_id=int(datetime.now(timezone.utc).timestamp() * 1000000) + saved,
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

    logger.info(
        f"Bot scenario '{scenario.scenario_name}' completed: "
        f"{result.steps_executed} steps, {len(result.collected_messages)} messages collected"
    )
    return result


async def _get_last_bot_message(
    client: TelegramClient, entity: object, limit: int = 5
) -> Optional[Message]:
    """Get the most recent message from the bot in the conversation."""
    async for msg in client.iter_messages(entity, limit=limit):
        if msg.out is False and msg.text:
            return msg
    return None


async def _click_inline_button(
    client: TelegramClient, message: Message, button_text: str
) -> bool:
    """Click an inline button by its text label."""
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
    """Click a reply keyboard button by sending its text."""
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
    """Collect recent messages from bot."""
    messages = []
    async for msg in client.iter_messages(entity, limit=limit):
        if msg.out is False and msg.text:
            messages.append(msg)
    messages.reverse()
    return messages
