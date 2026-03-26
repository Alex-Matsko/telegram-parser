"""
Logs API — exposes recent application log records via HTTP.

Uses an in-memory deque handler that is attached to the root logger
on first import.  The frontend polls GET /api/logs every few seconds
to display a live log viewer.
"""
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/logs", tags=["Logs"])

# ---------------------------------------------------------------------------
# In-memory log handler (singleton)
# ---------------------------------------------------------------------------

MAX_RECORDS = 1000  # keep last N log lines in memory


class _LogRecord(BaseModel):
    ts: str          # ISO timestamp
    level: str       # DEBUG / INFO / WARNING / ERROR / CRITICAL
    logger: str      # logger name
    message: str


_log_buffer: deque[_LogRecord] = deque(maxlen=MAX_RECORDS)


class _MemoryHandler(logging.Handler):
    """Appends formatted log records to the shared deque."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _log_buffer.append(
                _LogRecord(
                    ts=datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                    level=record.levelname,
                    logger=record.name,
                    message=self.format(record),
                )
            )
        except Exception:
            pass  # never let logging crash the app


def _install_handler() -> None:
    """Attach the memory handler to the root logger exactly once."""
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, _MemoryHandler):
            return  # already installed
    handler = _MemoryHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s [%(name)s] %(message)s")
    )
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)


_install_handler()

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


@router.get("", summary="Get recent log records")
async def get_logs(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Query(
        "INFO", description="Minimum log level to return"
    ),
    limit: int = Query(200, ge=1, le=1000, description="Max records to return"),
    logger_filter: str = Query("", description="Filter by logger name prefix (e.g. 'app.collector')"),
) -> dict:
    """
    Return the most recent *limit* log records from the in-memory buffer.

    Query params:
    - **level**: minimum level (DEBUG / INFO / WARNING / ERROR / CRITICAL)
    - **limit**: max number of records to return (newest last)
    - **logger_filter**: optional prefix to filter by logger name
    """
    min_level = LEVEL_ORDER.get(level, 1)
    records = [
        r for r in _log_buffer
        if LEVEL_ORDER.get(r.level, 0) >= min_level
        and (not logger_filter or r.logger.startswith(logger_filter))
    ]
    # return last `limit` records
    return {
        "total": len(records),
        "records": [r.model_dump() for r in records[-limit:]],
    }


@router.delete("", summary="Clear log buffer")
async def clear_logs() -> dict:
    """Wipe the in-memory log buffer."""
    _log_buffer.clear()
    return {"cleared": True}
