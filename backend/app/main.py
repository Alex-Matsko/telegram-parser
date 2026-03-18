"""FastAPI application entry point."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Price Aggregator",
    description="Aggregates electronics prices from Telegram sources",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Telegram Price Aggregator API")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Telegram Price Aggregator API")
    try:
        from app.collector.telegram_client import disconnect_telegram_client
        await disconnect_telegram_client()
    except Exception as e:
        logger.error(f"Error disconnecting Telegram client: {e}")

    from app.database import engine
    await engine.dispose()
    logger.info("Database engine disposed")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
