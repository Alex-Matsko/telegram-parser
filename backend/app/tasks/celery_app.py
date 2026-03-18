"""Celery application configuration."""
import logging

from celery import Celery
from celery.schedules import crontab

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
    # Worker reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Default timeouts for all tasks
    task_soft_time_limit=300,
    task_time_limit=360,
    beat_schedule={
        # ТЗ 4.2: collect every 15 minutes
        "collect-from-all-sources": {
            "task": "app.tasks.collect.collect_from_all_sources",
            "schedule": 900,  # 15 minutes
        },
        # ТЗ 4.3: bot scenarios every 30 minutes
        "execute-bot-scenarios": {
            "task": "app.tasks.collect.execute_all_bot_scenarios",
            "schedule": 1800,  # 30 minutes
        },
        # Parse pending messages every 5 minutes
        "parse-pending-messages": {
            "task": "app.tasks.parse.parse_pending_messages",
            "schedule": 300,  # 5 minutes
        },
        # Refresh price list every 10 minutes
        "refresh-price-list": {
            "task": "app.tasks.aggregate.refresh_price_list",
            "schedule": 600,  # 10 minutes
        },
    },
)
