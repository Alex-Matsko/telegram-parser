"""Collection tasks: read from Telegram channels and execute bot scenarios."""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Pause between sources to avoid Telegram FloodWaitError
_INTER_SOURCE_SLEEP_SEC = 1.0


def _run_async(coro):
    """Run an async coroutine in a fresh event loop (safe for Celery prefork)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_from_all_sources(self):
    """
    Periodic task: collect new messages from all active Telegram sources.
    Runs every 15 minutes via Celery Beat.
    """
    try:
        result = _run_async(_collect_from_all_sources_async())
        return result
    except Exception as exc:
        logger.error(f"Collection task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_from_source(self, source_id: int):
    """Collect messages from a single source."""
    try:
        result = _run_async(_collect_from_source_async(source_id))
        return result
    except Exception as exc:
        logger.error(f"Collection from source {source_id} failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def execute_all_bot_scenarios(self):
    """
    Periodic task: execute all active bot scenarios.
    Runs every 30 minutes via Celery Beat.
    """
    try:
        result = _run_async(_execute_all_bot_scenarios_async())
        return result
    except Exception as exc:
        logger.error(f"Bot scenario execution failed: {exc}")
        raise self.retry(exc=exc)


async def _collect_from_all_sources_async() -> dict:
    """Collect from all active sources with rate-limit pause between each."""
    from app.collector.channel_reader import get_active_sources, read_channel_messages
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session

    stats = {"sources_processed": 0, "messages_saved": 0, "errors": 0}

    async with get_telegram_client() as client:
        async with get_isolated_session() as session:
            sources = await get_active_sources(session)
            logger.info(f"Collecting from {len(sources)} active sources")

            for idx, source in enumerate(sources):
                if source.type == "bot":
                    # Bot sources are handled by execute_all_bot_scenarios
                    continue
                try:
                    saved = await read_channel_messages(
                        client=client,
                        source=source,
                        session=session,
                    )
                    stats["sources_processed"] += 1
                    stats["messages_saved"] += saved
                except Exception as e:
                    logger.error(f"Error collecting from {source.source_name}: {e}")
                    stats["errors"] += 1

                # Rate-limit: pause between sources to avoid FloodWaitError
                # Skip sleep after the last source
                if idx < len(sources) - 1:
                    await asyncio.sleep(_INTER_SOURCE_SLEEP_SEC)

            await session.commit()

    logger.info(f"Collection complete: {stats}")
    return stats


async def _collect_from_source_async(source_id: int) -> dict:
    """Collect from a single source."""
    from sqlalchemy import select

    from app.collector.channel_reader import read_channel_messages
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session
    from app.models.source import Source

    async with get_telegram_client() as client:
        async with get_isolated_session() as session:
            result = await session.execute(
                select(Source).where(Source.id == source_id)
            )
            source = result.scalar_one_or_none()
            if not source:
                return {"error": f"Source {source_id} not found"}

            saved = await read_channel_messages(
                client=client,
                source=source,
                session=session,
            )
            await session.commit()

    return {"source_id": source_id, "messages_saved": saved}


async def _execute_all_bot_scenarios_async() -> dict:
    """Execute all active bot scenarios."""
    from sqlalchemy import and_, select

    from app.collector.bot_interactor import execute_bot_scenario
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session
    from app.models.bot_scenario import BotScenario
    from app.models.source import Source

    stats = {"scenarios_executed": 0, "messages_collected": 0, "errors": 0}

    async with get_telegram_client() as client:
        async with get_isolated_session() as session:
            result = await session.execute(
                select(Source, BotScenario)
                .join(BotScenario, Source.bot_scenario_id == BotScenario.id)
                .where(
                    and_(
                        Source.is_active == True,  # noqa: E712
                        Source.type == "bot",
                        BotScenario.is_active == True,  # noqa: E712
                    )
                )
            )
            pairs = result.all()

            for idx, (source, scenario) in enumerate(pairs):
                try:
                    interaction = await execute_bot_scenario(
                        client=client,
                        source=source,
                        scenario=scenario,
                        session=session,
                    )
                    stats["scenarios_executed"] += 1
                    stats["messages_collected"] += len(interaction.collected_messages)
                    if interaction.errors:
                        stats["errors"] += len(interaction.errors)
                except Exception as e:
                    logger.error(
                        f"Error executing scenario {scenario.scenario_name}: {e}"
                    )
                    stats["errors"] += 1

                if idx < len(pairs) - 1:
                    await asyncio.sleep(_INTER_SOURCE_SLEEP_SEC)

            await session.commit()

    logger.info(f"Bot scenarios complete: {stats}")
    return stats
