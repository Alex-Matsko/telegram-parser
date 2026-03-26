"""Collection tasks: read from Telegram channels and execute bot scenarios."""
import asyncio
import logging
import time

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

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
    logger.info("[TASK:collect_from_all_sources] ▶ Task started")
    try:
        result = _run_async(_collect_from_all_sources_async())
        logger.info(f"[TASK:collect_from_all_sources] ✅ Task finished: {result}")
        return result
    except Exception as exc:
        logger.error(
            f"[TASK:collect_from_all_sources] ❌ Task failed: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_from_source(self, source_id: int):
    """Collect messages from a single source."""
    logger.info(f"[TASK:collect_from_source] ▶ Started for source_id={source_id}")
    try:
        result = _run_async(_collect_from_source_async(source_id))
        logger.info(
            f"[TASK:collect_from_source] ✅ Done for source_id={source_id}: {result}"
        )
        return result
    except Exception as exc:
        logger.error(
            f"[TASK:collect_from_source] ❌ Failed for source_id={source_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def execute_all_bot_scenarios(self):
    """
    Periodic task: execute all active bot scenarios.
    Runs every 30 minutes via Celery Beat.
    """
    logger.info("[TASK:execute_all_bot_scenarios] ▶ Task started")
    try:
        result = _run_async(_execute_all_bot_scenarios_async())
        logger.info(f"[TASK:execute_all_bot_scenarios] ✅ Task finished: {result}")
        return result
    except Exception as exc:
        logger.error(
            f"[TASK:execute_all_bot_scenarios] ❌ Task failed: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _collect_from_all_sources_async() -> dict:
    """Collect from all active sources with rate-limit pause between each."""
    from app.collector.channel_reader import get_active_sources, read_channel_messages
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session

    stats = {"sources_processed": 0, "messages_saved": 0, "errors": 0}
    task_start = time.monotonic()

    logger.info("[COLLECT] Connecting Telegram client ...")
    async with get_telegram_client() as client:
        logger.info("[COLLECT] Telegram client ready. Loading active sources from DB ...")
        async with get_isolated_session() as session:
            sources = await get_active_sources(session)
            channel_sources = [s for s in sources if s.type != "bot"]
            logger.info(
                f"[COLLECT] Found {len(sources)} active source(s) total | "
                f"{len(channel_sources)} channel/group | "
                f"{len(sources) - len(channel_sources)} bot (skipped here)"
            )

            for idx, source in enumerate(sources):
                if source.type == "bot":
                    logger.debug(
                        f"[COLLECT] Skipping bot source: {source.source_name} (id={source.id})"
                    )
                    continue

                src_start = time.monotonic()
                logger.info(
                    f"[COLLECT] [{idx + 1}/{len(sources)}] Processing source: "
                    f"'{source.source_name}' (id={source.id}, type={source.type})"
                )
                try:
                    saved = await read_channel_messages(
                        client=client,
                        source=source,
                        session=session,
                    )
                    elapsed = time.monotonic() - src_start
                    stats["sources_processed"] += 1
                    stats["messages_saved"] += saved
                    logger.info(
                        f"[COLLECT] [{idx + 1}/{len(sources)}] ✅ '{source.source_name}' — "
                        f"saved={saved} in {elapsed:.1f}s"
                    )
                except Exception as e:
                    elapsed = time.monotonic() - src_start
                    logger.error(
                        f"[COLLECT] [{idx + 1}/{len(sources)}] ❌ '{source.source_name}' — "
                        f"error after {elapsed:.1f}s: {type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    stats["errors"] += 1

                if idx < len(sources) - 1:
                    logger.debug(
                        f"[COLLECT] Sleeping {_INTER_SOURCE_SLEEP_SEC}s before next source ..."
                    )
                    await asyncio.sleep(_INTER_SOURCE_SLEEP_SEC)

            logger.info("[COLLECT] Committing DB session ...")
            await session.commit()
            logger.info("[COLLECT] DB commit done.")

    total_elapsed = time.monotonic() - task_start
    stats["elapsed_sec"] = round(total_elapsed, 2)
    logger.info(
        f"[COLLECT] ✅ All sources done: "
        f"processed={stats['sources_processed']} | "
        f"saved={stats['messages_saved']} | "
        f"errors={stats['errors']} | "
        f"elapsed={total_elapsed:.1f}s"
    )
    return stats


async def _collect_from_source_async(source_id: int) -> dict:
    """Collect from a single source."""
    from sqlalchemy import select

    from app.collector.channel_reader import read_channel_messages
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session
    from app.models.source import Source

    logger.info(f"[COLLECT:single] Connecting Telegram client for source_id={source_id} ...")
    async with get_telegram_client() as client:
        async with get_isolated_session() as session:
            logger.info(f"[COLLECT:single] Loading source_id={source_id} from DB ...")
            result = await session.execute(
                select(Source).where(Source.id == source_id)
            )
            source = result.scalar_one_or_none()
            if not source:
                logger.error(f"[COLLECT:single] ❌ Source id={source_id} not found in DB")
                return {"error": f"Source {source_id} not found"}

            logger.info(
                f"[COLLECT:single] Found source: '{source.source_name}' | "
                f"type={source.type} | telegram_id={source.telegram_id}"
            )
            start = time.monotonic()
            saved = await read_channel_messages(
                client=client,
                source=source,
                session=session,
            )
            elapsed = time.monotonic() - start
            logger.info("[COLLECT:single] Committing DB session ...")
            await session.commit()
            logger.info(
                f"[COLLECT:single] ✅ Done: source_id={source_id} | "
                f"saved={saved} | elapsed={elapsed:.1f}s"
            )

    return {"source_id": source_id, "messages_saved": saved, "elapsed_sec": round(elapsed, 2)}


async def _execute_all_bot_scenarios_async() -> dict:
    """Execute all active bot scenarios."""
    from sqlalchemy import and_, select

    from app.collector.bot_interactor import execute_bot_scenario
    from app.collector.telegram_client import get_telegram_client
    from app.database import get_isolated_session
    from app.models.bot_scenario import BotScenario
    from app.models.source import Source

    stats = {"scenarios_executed": 0, "messages_collected": 0, "errors": 0}
    task_start = time.monotonic()

    logger.info("[BOT_TASK] Connecting Telegram client ...")
    async with get_telegram_client() as client:
        logger.info("[BOT_TASK] Telegram client ready. Loading bot scenarios from DB ...")
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
            logger.info(f"[BOT_TASK] Found {len(pairs)} active bot scenario(s) to execute")

            for idx, (source, scenario) in enumerate(pairs):
                scen_start = time.monotonic()
                logger.info(
                    f"[BOT_TASK] [{idx + 1}/{len(pairs)}] Executing scenario "
                    f"'{scenario.scenario_name}' on '{source.source_name}' (id={source.id})"
                )
                try:
                    interaction = await execute_bot_scenario(
                        client=client,
                        source=source,
                        scenario=scenario,
                        session=session,
                    )
                    elapsed = time.monotonic() - scen_start
                    stats["scenarios_executed"] += 1
                    stats["messages_collected"] += len(interaction.collected_messages)
                    if interaction.errors:
                        stats["errors"] += len(interaction.errors)
                        logger.warning(
                            f"[BOT_TASK] [{idx + 1}/{len(pairs)}] ⚠ Scenario had errors: "
                            f"{interaction.errors}"
                        )
                    else:
                        logger.info(
                            f"[BOT_TASK] [{idx + 1}/{len(pairs)}] ✅ "
                            f"'{scenario.scenario_name}' — "
                            f"collected={len(interaction.collected_messages)} in {elapsed:.1f}s"
                        )
                except Exception as e:
                    elapsed = time.monotonic() - scen_start
                    logger.error(
                        f"[BOT_TASK] [{idx + 1}/{len(pairs)}] ❌ Scenario "
                        f"'{scenario.scenario_name}' failed after {elapsed:.1f}s: "
                        f"{type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    stats["errors"] += 1

                if idx < len(pairs) - 1:
                    logger.debug(
                        f"[BOT_TASK] Sleeping {_INTER_SOURCE_SLEEP_SEC}s before next scenario ..."
                    )
                    await asyncio.sleep(_INTER_SOURCE_SLEEP_SEC)

            logger.info("[BOT_TASK] Committing DB session ...")
            await session.commit()
            logger.info("[BOT_TASK] DB commit done.")

    total_elapsed = time.monotonic() - task_start
    stats["elapsed_sec"] = round(total_elapsed, 2)
    logger.info(
        f"[BOT_TASK] ✅ All scenarios done: "
        f"executed={stats['scenarios_executed']} | "
        f"collected={stats['messages_collected']} | "
        f"errors={stats['errors']} | "
        f"elapsed={total_elapsed:.1f}s"
    )
    return stats
