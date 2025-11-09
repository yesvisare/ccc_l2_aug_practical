"""
FastAPI Application for Module 7.3: Custom Business Metrics
===========================================================

Thin FastAPI app - all business logic is in src.m7_custom_business_metrics
"""

import logging
import os
from datetime import datetime

from fastapi import FastAPI
from src.m7_custom_business_metrics.api import router
from src.m7_custom_business_metrics.config import load_config, get_clients

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Module 7.3: Custom Business Metrics",
    description="REST API for RAG business metrics tracking and KPI generation",
    version="1.0.0"
)

# Include API router with /api prefix
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    """Health check endpoint."""
    config = load_config()
    clients = get_clients()

    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": "available" if clients['redis'] is not None else "not configured",
            "clickhouse": "available" if clients['clickhouse'] is not None else "not configured"
        }
    }


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    config = load_config()
    clients = get_clients()

    logger.info("Starting Module 7.3: Custom Business Metrics API")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Redis: {'Available' if clients['redis'] else 'Not configured'}")
    logger.info(f"ClickHouse: {'Available' if clients['clickhouse'] else 'Not configured'}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Module 7.3: Custom Business Metrics API")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
