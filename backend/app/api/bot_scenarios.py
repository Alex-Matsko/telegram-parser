"""Bot scenario management API endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.bot_scenario import BotScenario
from app.schemas.raw_message import (
    BotScenarioCreate,
    BotScenarioResponse,
    BotScenarioTestResult,
    BotScenarioUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot-scenarios", tags=["Bot Scenarios"])


@router.get("", response_model=list[BotScenarioResponse])
async def list_scenarios(
    session: AsyncSession = Depends(get_session),
) -> list[BotScenarioResponse]:
    """List all bot scenarios."""
    result = await session.execute(
        select(BotScenario).order_by(BotScenario.created_at.desc())
    )
    scenarios = result.scalars().all()
    return [BotScenarioResponse.model_validate(s) for s in scenarios]


@router.post("", response_model=BotScenarioResponse, status_code=201)
async def create_scenario(
    data: BotScenarioCreate,
    session: AsyncSession = Depends(get_session),
) -> BotScenarioResponse:
    """Create a new bot scenario."""
    scenario = BotScenario(
        bot_name=data.bot_name,
        scenario_name=data.scenario_name,
        steps_json=data.steps_json,
        is_active=data.is_active,
    )
    session.add(scenario)
    await session.flush()
    await session.refresh(scenario)
    return BotScenarioResponse.model_validate(scenario)


@router.put("/{scenario_id}", response_model=BotScenarioResponse)
async def update_scenario(
    scenario_id: int,
    data: BotScenarioUpdate,
    session: AsyncSession = Depends(get_session),
) -> BotScenarioResponse:
    """Update an existing bot scenario."""
    result = await session.execute(
        select(BotScenario).where(BotScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scenario, key, value)

    await session.flush()
    await session.refresh(scenario)
    return BotScenarioResponse.model_validate(scenario)


@router.post("/{scenario_id}/test", response_model=BotScenarioTestResult)
async def test_scenario(
    scenario_id: int,
    session: AsyncSession = Depends(get_session),
) -> BotScenarioTestResult:
    """Test-run a bot scenario (requires active Telegram connection)."""
    result = await session.execute(
        select(BotScenario).where(BotScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    try:
        from app.collector.telegram_client import get_telegram_client
        from app.collector.bot_interactor import execute_bot_scenario, BotInteractionResult
        from app.models.source import Source

        client = await get_telegram_client()

        # Find the source associated with this scenario
        source_result = await session.execute(
            select(Source).where(Source.bot_scenario_id == scenario_id).limit(1)
        )
        source = source_result.scalar_one_or_none()
        if not source:
            return BotScenarioTestResult(
                success=False,
                steps_executed=0,
                collected_messages=[],
                errors=["No source linked to this scenario. Link a source first."],
            )

        interaction_result = await execute_bot_scenario(
            client=client,
            source=source,
            scenario=scenario,
            session=session,
        )

        return BotScenarioTestResult(
            success=interaction_result.success,
            steps_executed=interaction_result.steps_executed,
            collected_messages=interaction_result.collected_messages,
            errors=interaction_result.errors,
        )

    except RuntimeError as e:
        return BotScenarioTestResult(
            success=False,
            steps_executed=0,
            collected_messages=[],
            errors=[f"Telegram client error: {e}"],
        )
    except Exception as e:
        logger.error(f"Scenario test failed: {e}")
        return BotScenarioTestResult(
            success=False,
            steps_executed=0,
            collected_messages=[],
            errors=[f"Unexpected error: {e}"],
        )
