"""
Telegram client management for Celery workers.

Each call creates a fresh TelegramClient bound to the current event loop.
In Celery prefork mode, each task invocation gets its own event loop,
so clients cannot be cached across calls.

Proxy pool: set TELEGRAM_PROXY_LIST=host1:port1,host2:port2,...
On connection failure the next proxy is tried automatically.
Single proxy fallback: TELEGRAM_PROXY_HOST / TELEGRAM_PROXY_PORT still work.
"""
import logging
from contextlib import asynccontextmanager

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_proxy_list() -> list[tuple]:
    """
    Parse proxy pool from TELEGRAM_PROXY_LIST env var.
    Format: host1:port1,host2:port2,...
    Falls back to single TELEGRAM_PROXY_HOST/PORT if list is empty.
    Returns list of (socks.SOCKS5, host, port) tuples.
    """
    import socks

    proxies = []

    # Try pool list first
    proxy_list_str = getattr(settings, "telegram_proxy_list", "") or ""
    for entry in proxy_list_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            parts = entry.rsplit(":", 1)
            host, port = parts[0].strip(), parts[1].strip()
            if host and port.isdigit():
                proxies.append((socks.SOCKS5, host, int(port)))

    # Fall back to single proxy
    if not proxies:
        host = getattr(settings, "telegram_proxy_host", None)
        port = getattr(settings, "telegram_proxy_port", None)
        if host and port:
            proxies.append((socks.SOCKS5, host, int(port)))

    return proxies


@asynccontextmanager
async def get_telegram_client():
    """
    Async context manager that creates, connects, and disposes a
    TelegramClient tied to the current event loop.

    Tries each proxy in the pool sequentially on connection failure.
    If all proxies fail, raises the last ConnectionError.

    Usage:
        async with get_telegram_client() as client:
            ...
    """
    try:
        proxies = _parse_proxy_list()
    except ImportError:
        proxies = []

    # No proxy configured — connect directly
    if not proxies:
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
        logger.info("Telegram client connected (no proxy)")
        try:
            yield client
        finally:
            await client.disconnect()
            logger.info("Telegram client disconnected")
        return

    # Try proxies one by one
    last_error = None
    for i, proxy in enumerate(proxies):
        logger.info(
            "Telegram client trying proxy %d/%d: %s:%s",
            i + 1, len(proxies), proxy[1], proxy[2],
        )
        client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            proxy=proxy,
        )
        try:
            await client.connect()
        except Exception as e:
            logger.warning(
                "Proxy %s:%s failed: %s — trying next",
                proxy[1], proxy[2], e,
            )
            last_error = e
            try:
                await client.disconnect()
            except Exception:
                pass
            continue

        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError(
                "Telegram client is not authorized. "
                "Please provide a valid session string."
            )

        logger.info(
            "Telegram client connected via proxy %s:%s",
            proxy[1], proxy[2],
        )
        try:
            yield client
        finally:
            await client.disconnect()
            logger.info("Telegram client disconnected")
        return

    raise ConnectionError(
        f"All {len(proxies)} proxy(ies) failed. Last error: {last_error}"
    )


async def disconnect_telegram_client():
    """
    Stub for graceful shutdown compatibility.
    Actual cleanup is handled by the context manager above.
    Called during FastAPI shutdown event.
    """
    logger.info("Telegram client cleanup: handled by context manager, no persistent client to disconnect.")
