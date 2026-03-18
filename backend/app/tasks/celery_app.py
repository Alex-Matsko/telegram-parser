"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "price_aggregator",
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
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "collect-from-sources": {
        "task": "app.tasks.collect.collect_from_all_sources",
        "schedule": crontab(minute="*/15"),
    },
    "execute-bot-scenarios": {
        "task": "app.tasks.collect.execute_all_bot_scenarios",
        "schedule": crontab(minute="*/30"),
    },
    "parse-raw-messages": {
        "task": "app.tasks.parse.parse_pending_messages",
        "schedule": crontab(minute="*/5"),
    },
    "refresh-price-list": {
        "task": "app.tasks.aggregate.refresh_price_list",
        "schedule": crontab(minute="*/10"),
    },
}
