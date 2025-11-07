"""
FastAPI application for M5.1 Incremental Indexing.

Provides REST API endpoints for:
- Health checks
- Incremental index updates
- Change detection
- Version management
- Query operations
"""

import logging
import os
from typing import List, Dict, Optional
from glob import glob

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import core module functions
from l2_m5_1_incremental_indexing import (
    ChangeDetector,
    IncrementalIndexer,
    IndexVersionManager,
    simple_chunk_function
)
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M5.1 Incremental Indexing API",
    description="Efficient incremental updates for vector databases",
    version="1.0.0"
)

# Global state (initialized on startup)
detector: Optional[ChangeDetector] = None
indexer: Optional[IncrementalIndexer] = None
version_manager: Optional[IndexVersionManager] = None
clients: Dict = {}


# Pydantic models for request/response
class HealthResponse(BaseModel):
    status: str
    message: str
    services: Dict[str, bool]


class DetectChangesRequest(BaseModel):
    documents_glob: str = Field(
        default="example_documents/**/*.txt",
        description="Glob pattern for document paths"
    )


class DetectChangesResponse(BaseModel):
    new: List[str]
    modified: List[str]
    deleted: List[str]
    unchanged: List[str]
    total_changed: int


class UpdateIndexRequest(BaseModel):
    documents_glob: str = Field(
        default="example_documents/**/*.txt",
        description="Glob pattern for document paths"
    )
    create_snapshot: bool = Field(
        default=True,
        description="Create version snapshot before update"
    )


class UpdateIndexResponse(BaseModel):
    skipped: Optional[bool] = None
    reason: Optional[str] = None
    new: Optional[int] = None
    modified: Optional[int] = None
    deleted: Optional[int] = None
    unchanged: Optional[int] = None
    duration_seconds: Optional[float] = None
    snapshot_id: Optional[str] = None


class QueryRequest(BaseModel):
    query_text: str = Field(..., description="Query text for similarity search")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to return")


class QueryResponse(BaseModel):
    skipped: Optional[bool] = None
    reason: Optional[str] = None
    results: Optional[List[Dict]] = None
    query_time_seconds: Optional[float] = None


class SnapshotResponse(BaseModel):
    snapshot_id: str
    message: str


class SnapshotListResponse(BaseModel):
    snapshots: List[str]
    count: int


class RollbackRequest(BaseModel):
    snapshot_id: str = Field(..., description="Snapshot ID to rollback to")


@app.on_event("startup")
async def startup_event():
    """Initialize clients and services on startup."""
    global detector, indexer, version_manager, clients

    logger.info("Initializing M5.1 Incremental Indexing API...")

    # Initialize change detector
    detector = ChangeDetector(state_file=config.DEFAULT_STATE_FILE)

    # Initialize version manager
    version_manager = IndexVersionManager(
        versions_dir=config.DEFAULT_VERSIONS_DIR,
        max_versions=config.DEFAULT_MAX_VERSIONS
    )

    # Get clients (will gracefully handle missing keys)
    clients = config.get_clients()

    # Initialize indexer if clients available
    if 'index' in clients and 'embed_fn' in clients:
        indexer = IncrementalIndexer(
            index_client=clients['index'],
            change_detector=detector,
            embedding_function=clients['embed_fn'],
            chunk_function=simple_chunk_function,
            batch_size=config.DEFAULT_BATCH_SIZE
        )
        logger.info("✓ Incremental indexer initialized with live services")
    else:
        logger.warning("⚠ Running in mock mode (no API keys configured)")

    logger.info("API startup complete")


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with service status."""
    return HealthResponse(
        status="ok",
        message="M5.1 Incremental Indexing API is running",
        services={
            "pinecone": 'index' in clients,
            "openai": 'openai' in clients,
            "change_detector": detector is not None,
            "version_manager": version_manager is not None
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        message="All systems operational",
        services={
            "pinecone": 'index' in clients,
            "openai": 'openai' in clients,
            "change_detector": detector is not None,
            "version_manager": version_manager is not None
        }
    )


@app.post("/detect-changes", response_model=DetectChangesResponse)
async def detect_changes(request: DetectChangesRequest):
    """
    Detect changes in document corpus without updating index.

    This endpoint is fast and can be called frequently to monitor changes.
    """
    if not detector:
        raise HTTPException(status_code=500, detail="Change detector not initialized")

    try:
        # Find documents matching glob pattern
        document_paths = glob(request.documents_glob, recursive=True)

        if not document_paths:
            raise HTTPException(
                status_code=400,
                detail=f"No documents found matching pattern: {request.documents_glob}"
            )

        # Detect changes
        report = detector.detect_changes(document_paths)

        return DetectChangesResponse(
            new=report.new,
            modified=report.modified,
            deleted=report.deleted,
            unchanged=report.unchanged,
            total_changed=report.total_changed
        )

    except Exception as e:
        logger.error(f"Change detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-index", response_model=UpdateIndexResponse)
async def update_index(request: UpdateIndexRequest, background_tasks: BackgroundTasks):
    """
    Run incremental index update.

    This endpoint processes detected changes and updates the vector index.
    Returns 200 with skipped=true if no API keys configured.
    """
    if not detector:
        raise HTTPException(status_code=500, detail="Change detector not initialized")

    # Check if services are available
    if not indexer or 'index' not in clients:
        return UpdateIndexResponse(
            skipped=True,
            reason="No Pinecone API key configured (running in mock mode)"
        )

    try:
        # Create snapshot before update
        snapshot_id = None
        if request.create_snapshot and version_manager:
            snapshot_id = version_manager.create_snapshot(config.DEFAULT_STATE_FILE)

        # Find documents
        document_paths = glob(request.documents_glob, recursive=True)

        if not document_paths:
            raise HTTPException(
                status_code=400,
                detail=f"No documents found matching pattern: {request.documents_glob}"
            )

        # Run incremental update
        stats = indexer.run_incremental_update(document_paths)

        return UpdateIndexResponse(
            new=stats.get("new", 0),
            modified=stats.get("modified", 0),
            deleted=stats.get("deleted", 0),
            unchanged=stats.get("unchanged", 0),
            duration_seconds=stats.get("duration_seconds", 0),
            snapshot_id=snapshot_id
        )

    except Exception as e:
        logger.error(f"Index update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query_index(request: QueryRequest):
    """
    Query the vector index for similar documents.

    Returns 200 with skipped=true if no API keys configured.
    """
    if not indexer or 'index' not in clients:
        return QueryResponse(
            skipped=True,
            reason="No Pinecone API key configured (running in mock mode)"
        )

    try:
        import time
        start_time = time.time()

        # Generate query embedding
        query_embedding = clients['embed_fn'](request.query_text)

        # Query index
        results = clients['index'].query(
            vector=query_embedding,
            top_k=request.top_k,
            include_metadata=True
        )

        query_time = time.time() - start_time

        # Format results
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                "id": match.id,
                "score": float(match.score),
                "metadata": match.metadata
            })

        return QueryResponse(
            results=formatted_results,
            query_time_seconds=query_time
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/snapshot", response_model=SnapshotResponse)
async def create_snapshot():
    """Create a version snapshot of current index state."""
    if not version_manager:
        raise HTTPException(status_code=500, detail="Version manager not initialized")

    try:
        snapshot_id = version_manager.create_snapshot(config.DEFAULT_STATE_FILE)
        return SnapshotResponse(
            snapshot_id=snapshot_id,
            message=f"Snapshot created successfully: {snapshot_id}"
        )
    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/snapshots", response_model=SnapshotListResponse)
async def list_snapshots():
    """List available version snapshots."""
    if not version_manager:
        raise HTTPException(status_code=500, detail="Version manager not initialized")

    try:
        snapshots = version_manager.list_snapshots()
        return SnapshotListResponse(
            snapshots=snapshots,
            count=len(snapshots)
        )
    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rollback", response_model=SnapshotResponse)
async def rollback_to_snapshot(request: RollbackRequest):
    """Rollback to a previous version snapshot."""
    if not version_manager:
        raise HTTPException(status_code=500, detail="Version manager not initialized")

    try:
        version_manager.rollback_to_snapshot(request.snapshot_id, config.DEFAULT_STATE_FILE)

        # Reload detector state after rollback
        if detector:
            detector._load_state()

        return SnapshotResponse(
            snapshot_id=request.snapshot_id,
            message=f"Successfully rolled back to snapshot: {request.snapshot_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Optional: Prometheus metrics endpoint
if config.ENABLE_METRICS:
    try:
        from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

        # Define metrics
        change_detection_duration = Histogram(
            'change_detection_duration_seconds',
            'Time spent detecting changes'
        )
        update_counter = Counter(
            'index_updates_total',
            'Total number of index updates',
            ['status']
        )

        @app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            return JSONResponse(
                content=generate_latest().decode('utf-8'),
                media_type=CONTENT_TYPE_LATEST
            )

        logger.info(f"✓ Metrics enabled at /metrics")
    except ImportError:
        logger.warning("prometheus-client not installed, metrics disabled")


if __name__ == "__main__":
    """Run the API server locally."""
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
