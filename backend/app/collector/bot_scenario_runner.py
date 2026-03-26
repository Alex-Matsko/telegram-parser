"""
Executes a BotScenario (steps_json) before reading messages from a bot source.

steps_json format (list of step objects):

  [{"action": "send",    "text": "Прайс"},
   {"action": "wait",    "seconds": 3},
   {"action": "send",    "text": "/start"},
   {"action": "click",   "button": "Прайс"},   # inline / reply button by label
   {"action": "wait",    "seconds": 5}]

Supported actions:
  send    — send a text message to the bot
  wait    — sleep N seconds (default 3)
  click   — press an inline or reply-keyboard button by its label text
"""
import asyncio
import logging
from typing import Any

from telethon import TelegramClient
from telethon.tl.custom import Button
from telethon.tl.types import (
    KeyboardButtonCallback,
    KeyboardButtonRow,
    ReplyInlineMarkup,
    ReplyKeyboardMarkup,
)

logger = logging.getLogger(__name__)

_DEFAULT_WAIT = 3
_DEFAULT_RESPONSE_TIMEOUT = 8


async def run_scenario(
    client: TelegramClient,
    entity,
    steps: list[dict[str, Any]],
    source_name: str = "bot",
) -> None:
    """
    Execute a list of scenario steps against `entity` (a resolved bot entity).
    """
    for i, step in enumerate(steps):
        action = step.get("action", "").lower()

        if action == "send":
            text = step.get("text", "")
            if not text:
                logger.warning(f"[{source_name}] step {i}: 'send' action has empty text, skipping")
                continue
            await client.send_message(entity, text)
            logger.info(f"[{source_name}] step {i}: sent message {text!r}")

        elif action == "wait":
            seconds = float(step.get("seconds", _DEFAULT_WAIT))
            logger.info(f"[{source_name}] step {i}: waiting {seconds}s")
            await asyncio.sleep(seconds)

        elif action == "click":
            button_label = step.get("button", "")
            if not button_label:
                logger.warning(f"[{source_name}] step {i}: 'click' action has empty button label, skipping")
                continue
            await _click_button(client, entity, button_label, source_name, step_index=i)

        else:
            logger.warning(f"[{source_name}] step {i}: unknown action {action!r}, skipping")


async def _click_button(
    client: TelegramClient,
    entity,
    label: str,
    source_name: str,
    step_index: int,
) -> None:
    """
    Find the most recent message from the bot that contains a button
    matching `label` and click it.
    """
    async for message in client.iter_messages(entity, limit=10):
        if not message.buttons:
            continue
        for row in message.buttons:
            # message.buttons is list[list[Button]]
            buttons = row if isinstance(row, list) else [row]
            for btn in buttons:
                btn_text = getattr(btn, "text", "") or ""
                if btn_text.strip().lower() == label.strip().lower():
                    try:
                        await message.click(btn)
                        logger.info(
                            f"[{source_name}] step {step_index}: "
                            f"clicked button {label!r} in message id={message.id}"
                        )
                        return
                    except Exception as e:
                        logger.error(
                            f"[{source_name}] step {step_index}: "
                            f"failed to click button {label!r}: {e}"
                        )
                        return

    logger.warning(
        f"[{source_name}] step {step_index}: "
        f"button {label!r} not found in last 10 messages"
    )
