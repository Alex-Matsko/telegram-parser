"""Celery application configuration."""
import logging

from celery import Celery
from celery.schedules import crontab  # noqa: F401  kept for future use
from celery.signals import worker_process_init

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "telegram_parser",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.collect",
        "app.tasks.parse",
        "app.tasks.aggregate",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=3600,
    task_time_limit=3660,
    beat_schedule={
        "collect-from-all-sources": {
            "task": "app.tasks.collect.collect_from_all_sources",
            "schedule": 900,
        },
        "execute-bot-scenarios": {
            "task": "app.tasks.collect.execute_all_bot_scenarios",
            "schedule": 1800,
        },
        "parse-pending-messages": {
            "task": "app.tasks.parse.parse_pending_messages",
            "schedule": 60,
        },
        "refresh-price-list": {
            "task": "app.tasks.aggregate.refresh_price_list",
            "schedule": 600,
        },
    },
)


@worker_process_init.connect
def setup_worker_logging(**kwargs):
    """
    Install RedisLogHandler in every Celery worker process so that
    all task logs (collect, parse, aggregate) appear in the frontend log viewer.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    from app.api.logs import _install_handler
    _install_handler()
    logging.getLogger(__name__).info(
        "[Celery worker] RedisLogHandler installed — logs will appear in frontend"
    )
