"""
Executes a BotScenario (steps_json) before reading messages from a bot source.

steps_json format — list of step objects matching the UI BotScenarioEditor:

  [
    {"action": "send_command",     "value": "/start",   "wait_sec": 2},
    {"action": "send_text",        "value": "Прайс",   "wait_sec": 3},
    {"action": "click_inline",     "value": "Прайс",   "wait_sec": 5},
    {"action": "click_reply",      "value": "Прайс",   "wait_sec": 5},
    {"action": "collect_response", "value": "",         "wait_sec": 0},
    {"action": "wait",             "value": "",         "wait_sec": 3},
  ]

Supported actions:
  send_command     — send text/command to the bot (same as send_text)
  send_text        — send text message to the bot
  click_inline     — click inline keyboard button by label
  click_reply      — click reply keyboard button by label
  collect_response — no-op marker; collector reads messages after scenario finishes
  wait             — sleep wait_sec seconds

After each step the runner sleeps `wait_sec` seconds (0 by default).
"""
import asyncio
import logging
from typing import Any

from telethon import TelegramClient

logger = logging.getLogger(__name__)


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
        value = step.get("value", "") or ""
        wait_sec = float(step.get("wait_sec", 0))

        if action in ("send_command", "send_text"):
            if not value:
                logger.warning(
                    f"[{source_name}] step {i}: '{action}' has empty value, skipping"
                )
            else:
                await client.send_message(entity, value)
                logger.info(
                    f"[{source_name}] step {i}: [{action}] sent {value!r}"
                )

        elif action in ("click_inline", "click_reply"):
            if not value:
                logger.warning(
                    f"[{source_name}] step {i}: '{action}' has empty button label, skipping"
                )
            else:
                await _click_button(client, entity, value, source_name, step_index=i)

        elif action == "collect_response":
            # Marker step — actual collection happens in channel_reader after scenario
            logger.info(
                f"[{source_name}] step {i}: [collect_response] marker, no action"
            )

        elif action == "wait":
            logger.info(
                f"[{source_name}] step {i}: [wait] sleeping {wait_sec}s"
            )

        else:
            logger.warning(
                f"[{source_name}] step {i}: unknown action {action!r}, skipping"
            )
            continue  # don't sleep for unknown actions

        if wait_sec > 0:
            await asyncio.sleep(wait_sec)


async def _click_button(
    client: TelegramClient,
    entity,
    label: str,
    source_name: str,
    step_index: int,
) -> None:
    """
    Find the most recent message from the bot containing a button
    matching `label` (case-insensitive) and click it.
    """
    async for message in client.iter_messages(entity, limit=10):
        if not message.buttons:
            continue
        for row in message.buttons:
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
