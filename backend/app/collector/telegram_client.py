"""
Telegram client management for Celery workers.

Each call creates a fresh TelegramClient bound to the current event loop.
In Celery prefork mode, each task invocation gets its own event loop,
so clients cannot be cached across calls.
"""
import logging
from contextlib import asynccontextmanager

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_telegram_client():
    """
    Async context manager that creates, connects, and disposes a
    TelegramClient tied to the current event loop.

    Usage:
        async with get_telegram_client() as client:
            ...
    """
    client = TelegramClient(
        StringSession(settings.telegram_session_string),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(
            "Telegram client is not authorized. "
            "Please provide a valid session string."
        )

    logger.info("Telegram client connected successfully")
    try:
        yield client
    finally:
        await client.disconnect()
        logger.info("Telegram client disconnected")


async def disconnect_telegram_client():
    """
    Stub for graceful shutdown compatibility.
    Actual cleanup is handled by the context manager above.
    Called during FastAPI shutdown event.
    """
    logger.info("Telegram client cleanup: handled by context manager, no persistent client to disconnect.")
