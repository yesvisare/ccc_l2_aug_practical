"""
FastAPI entrypoint for M5.2: Data Pipelines & Orchestration.
Provides REST API endpoints for triggering pipeline operations.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from datetime import datetime

# Import our module functions
from l2_m2_datapipelines_orchestration import (
    detect_changed_documents,
    run_incremental_refresh_pipeline
)

from config import (
    DATA_DIR,
    CHECKSUM_FILE,
    BATCH_SIZE,
    MAX_WORKERS,
    get_clients,
    validate_config
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M5.2: Data Pipelines & Orchestration API",
    description="REST API for automated RAG data refresh pipelines",
    version="1.0.0"
)

# Optional prometheus metrics
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    # Define metrics
    pipeline_runs = Counter('pipeline_runs_total', 'Total pipeline executions', ['status'])
    pipeline_duration = Histogram('pipeline_duration_seconds', 'Pipeline execution duration')
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("prometheus-client not installed. Metrics endpoint disabled.")


# Request models
class RefreshRequest(BaseModel):
    """Request model for triggering pipeline refresh."""
    documents_path: Optional[str] = None
    max_workers: Optional[int] = None


class QueryRequest(BaseModel):
    """Request model for querying pipeline status."""
    documents_path: Optional[str] = None


# Global state (in production, use a proper state store)
pipeline_state = {
    "last_run": None,
    "status": "idle",
    "result": None
}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "M5.2: Data Pipelines & Orchestration",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "detect": "/detect",
            "refresh": "/refresh (POST)",
            "status": "/status",
            "metrics": "/metrics (if prometheus-client installed)"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns service status and configuration validation.
    """
    config_valid = validate_config()
    clients = get_clients()

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "valid": config_valid,
            "openai_configured": clients['openai'] is not None,
            "pinecone_configured": clients['pinecone'] is not None
        },
        "pipeline": {
            "status": pipeline_state["status"],
            "last_run": pipeline_state["last_run"]
        }
    }


@app.get("/detect")
async def detect_changes(documents_path: Optional[str] = None):
    """
    Detect changed documents without processing them.

    Args:
        documents_path: Optional path to documents directory (defaults to config)

    Returns:
        Dictionary with changed and deleted files
    """
    try:
        path = documents_path or DATA_DIR
        result = detect_changed_documents(path, CHECKSUM_FILE)

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "changed_files": len(result['changed_files']),
            "deleted_files": len(result['deleted_files']),
            "files": {
                "changed": result['changed_files'][:10],  # Limit to first 10
                "deleted": result['deleted_files'][:10]
            },
            "note": "Showing first 10 files only" if len(result['changed_files']) > 10 else None
        }
    except Exception as e:
        logger.error(f"Error detecting changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/refresh")
async def trigger_refresh(request: RefreshRequest, background_tasks: BackgroundTasks):
    """
    Trigger incremental refresh pipeline.

    This endpoint runs the full pipeline: detect changes, process documents,
    embed, and upsert to vector database.

    Args:
        request: RefreshRequest with optional parameters
        background_tasks: FastAPI background tasks

    Returns:
        Status and execution summary
    """
    # Check if already running
    if pipeline_state["status"] == "running":
        return JSONResponse(
            status_code=409,
            content={
                "status": "error",
                "message": "Pipeline already running",
                "current_state": pipeline_state
            }
        )

    # Get clients
    clients = get_clients()

    # Check configuration
    if not validate_config():
        return {
            "status": "skipped",
            "reason": "Configuration incomplete (API keys missing)",
            "message": "⚠️ Skipping API calls. Set OPENAI_API_KEY and PINECONE_API_KEY in .env",
            "timestamp": datetime.now().isoformat()
        }

    # Run pipeline in background
    def run_pipeline():
        try:
            pipeline_state["status"] = "running"
            pipeline_state["last_run"] = datetime.now().isoformat()

            if METRICS_ENABLED:
                with pipeline_duration.time():
                    result = run_incremental_refresh_pipeline(
                        documents_path=request.documents_path or DATA_DIR,
                        checksums_file=CHECKSUM_FILE,
                        openai_client=clients['openai'],
                        pinecone_index=clients['pinecone'],
                        max_workers=request.max_workers or MAX_WORKERS
                    )
                pipeline_runs.labels(status=result['status']).inc()
            else:
                result = run_incremental_refresh_pipeline(
                    documents_path=request.documents_path or DATA_DIR,
                    checksums_file=CHECKSUM_FILE,
                    openai_client=clients['openai'],
                    pinecone_index=clients['pinecone'],
                    max_workers=request.max_workers or MAX_WORKERS
                )

            pipeline_state["status"] = "idle"
            pipeline_state["result"] = result

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            pipeline_state["status"] = "error"
            pipeline_state["result"] = {"error": str(e)}
            if METRICS_ENABLED:
                pipeline_runs.labels(status="error").inc()

    background_tasks.add_task(run_pipeline)

    return {
        "status": "started",
        "message": "Pipeline execution started in background",
        "timestamp": datetime.now().isoformat(),
        "check_status_at": "/status"
    }


@app.get("/status")
async def get_status():
    """
    Get current pipeline status and last execution result.

    Returns:
        Current pipeline state including last run details
    """
    return {
        "status": pipeline_state["status"],
        "last_run": pipeline_state["last_run"],
        "result": pipeline_state["result"],
        "timestamp": datetime.now().isoformat()
    }


if METRICS_ENABLED:
    @app.get("/metrics")
    async def metrics():
        """
        Prometheus metrics endpoint.
        Only available if prometheus-client is installed.
        """
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )


if __name__ == "__main__":
    import uvicorn

    print("=== M5.2: Data Pipelines & Orchestration API ===")
    print("\nStarting server...")
    print("Docs available at: http://localhost:8000/docs")
    print("Health check: http://localhost:8000/health")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
