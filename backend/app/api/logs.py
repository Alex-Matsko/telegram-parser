"""
Logs API — live log viewer backed by Redis.

Architecture:
  - RedisLogHandler writes every log record as a JSON string into a Redis List
    (key: app:logs). The list is capped at MAX_RECORDS via LTRIM.
  - The handler is installed on the root logger by _install_handler().
  - Both FastAPI process AND Celery workers call _install_handler() on import,
    so all log records from all processes end up in the same Redis list.
  - GET /api/logs reads from Redis, filters by level / logger prefix, returns
    the last N records.
  - DELETE /api/logs wipes the Redis list.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Literal

import redis
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/logs", tags=["Logs"])

REDIS_KEY = "app:logs"
MAX_RECORDS = 2000


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class LogRecord(BaseModel):
    ts: str
    level: str
    logger: str
    message: str


# ---------------------------------------------------------------------------
# Redis client (sync — logging handlers must be sync)
# ---------------------------------------------------------------------------

def _get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Redis log handler
# ---------------------------------------------------------------------------

class RedisLogHandler(logging.Handler):
    """Appends formatted log records to a Redis list shared across all processes."""

    def __init__(self) -> None:
        super().__init__()
        try:
            self._redis = _get_redis()
        except Exception:
            self._redis = None

    def emit(self, record: logging.LogRecord) -> None:
        if self._redis is None:
            return
        try:
            payload = json.dumps({
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
            pipe = self._redis.pipeline()
            pipe.rpush(REDIS_KEY, payload)
            pipe.ltrim(REDIS_KEY, -MAX_RECORDS, -1)
            pipe.execute()
        except Exception:
            pass  # never let logging crash the app


def _install_handler() -> None:
    """Attach RedisLogHandler to the root logger exactly once per process."""
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, RedisLogHandler):
            return
    handler = RedisLogHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)


_install_handler()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


def _read_records(
    min_level: str,
    limit: int,
    logger_filter: str,
) -> list[LogRecord]:
    try:
        r = _get_redis()
        raw_list = r.lrange(REDIS_KEY, 0, -1)
    except Exception:
        return []

    min_order = LEVEL_ORDER.get(min_level, 1)
    result: list[LogRecord] = []
    for raw in raw_list:
        try:
            data = json.loads(raw)
            if LEVEL_ORDER.get(data.get("level", ""), 0) < min_order:
                continue
            if logger_filter and not data.get("logger", "").startswith(logger_filter):
                continue
            result.append(LogRecord(**data))
        except Exception:
            continue

    return result[-limit:]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", summary="Get recent log records")
async def get_logs(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Query(
        "INFO", description="Minimum log level to return"
    ),
    limit: int = Query(300, ge=1, le=2000, description="Max records to return"),
    logger_filter: str = Query("", description="Filter by logger name prefix (e.g. 'app.collector')"),
) -> dict:
    records = _read_records(level, limit, logger_filter)
    return {
        "total": len(records),
        "records": [r.model_dump() for r in records],
    }


@router.delete("", summary="Clear log buffer")
async def clear_logs() -> dict:
    try:
        r = _get_redis()
        r.delete(REDIS_KEY)
    except Exception:
        pass
    return {"cleared": True}
