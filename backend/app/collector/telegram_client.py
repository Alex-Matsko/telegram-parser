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


def _get_proxy():
    """Return proxy tuple for Telethon if configured, else None."""
    host = getattr(settings, "telegram_proxy_host", None)
    port = getattr(settings, "telegram_proxy_port", None)
    if host and port:
        import socks
        return (socks.SOCKS5, host, int(port))
    return None


@asynccontextmanager
async def get_telegram_client():
    """
    Async context manager that creates, connects, and disposes a
    TelegramClient tied to the current event loop.

    Usage:
        async with get_telegram_client() as client:
            ...
    """
    proxy = _get_proxy()
    if proxy:
        logger.info("Telegram client using SOCKS5 proxy %s:%s", proxy[1], proxy[2])

    client = TelegramClient(
        StringSession(settings.telegram_session_string),
        settings.telegram_api_id,
        settings.telegram_api_hash,
        proxy=proxy,
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
