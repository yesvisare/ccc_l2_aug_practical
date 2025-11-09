"""
Thin FastAPI app for Module 7.4: Intelligent Alerting.

All business logic and routes are in src.m7_intelligent_alerting_workspace.
"""

import os
from fastapi import FastAPI
from src.m7_intelligent_alerting_workspace.api import router, initialize_services

# Create FastAPI app
app = FastAPI(
    title="Module 7 — Intelligent Alerting Workspace",
    description="Statistical anomaly detection and alert aggregation",
    version="1.0.0"
)

# Mount API router
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    """Root health check."""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    initialize_services()


# Local development runner
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload
    )
