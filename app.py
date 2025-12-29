"""
Module 7.2: Application Performance Monitoring - FastAPI Entrypoint
Provides REST API for APM-instrumented RAG pipeline.

No business logic in this file - all functionality imported from
l2_m7_application_performance_monitoring.py
"""

import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import core functionality
from config import apm_config
from l2_m7_application_performance_monitoring import (
    APMManager,
    ProfiledRAGPipeline,
    MemoryProfiler,
    QueryCache
)

# Prometheus metrics (optional)
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    METRICS_AVAILABLE = True

    # Define metrics
    query_counter = Counter('rag_queries_total', 'Total RAG queries processed')
    query_duration = Histogram('rag_query_duration_seconds', 'RAG query duration')
except ImportError:
    METRICS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Request/Response models
class QueryRequest(BaseModel):
    """Request model for RAG query."""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    use_cache: bool = Field(default=True, description="Whether to use query cache")


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    response: str
    context_size: int
    num_results: int
    cached: bool = False
    apm_enabled: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    apm_enabled: bool
    apm_initialized: bool


class MemoryStatsResponse(BaseModel):
    """Memory statistics response."""
    current_mb: float
    peak_mb: float
    baseline_mb: float
    growth_mb: float


# Initialize APM and components
apm_manager = APMManager(apm_config)
pipeline: ProfiledRAGPipeline = None  # Will be initialized on startup
memory_profiler: MemoryProfiler = None
query_cache = QueryCache(max_size=1000)


def create_app() -> FastAPI:
    """
    Create FastAPI application with APM instrumentation.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="Module 7.2: Application Performance Monitoring",
        description="APM-instrumented RAG pipeline with Datadog integration",
        version="1.0.0"
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize APM on application startup."""
        global pipeline, memory_profiler

        logger.info("Starting application...")

        # Initialize APM
        if apm_config.is_enabled():
            try:
                success = apm_manager.initialize()
                if success:
                    logger.info("✅ APM initialized successfully")
                else:
                    logger.warning("⚠️  APM initialization failed - running without APM")
            except Exception as e:
                logger.error(f"❌ APM initialization error: {e}")
        else:
            logger.info("⚠️  APM disabled (DD_API_KEY not set)")

        # Initialize pipeline and profiler
        pipeline = ProfiledRAGPipeline(use_apm=apm_manager.is_initialized())
        memory_profiler = MemoryProfiler()

        logger.info("Application startup complete")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Graceful shutdown of APM."""
        logger.info("Shutting down application...")
        apm_manager.shutdown()
        logger.info("Application shutdown complete")

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """
        Health check endpoint.

        Returns:
            Service health status and APM state
        """
        return HealthResponse(
            status="ok",
            apm_enabled=apm_config.is_enabled(),
            apm_initialized=apm_manager.is_initialized()
        )

    @app.post("/query", response_model=QueryResponse)
    async def process_query(request: QueryRequest) -> QueryResponse:
        """
        Process RAG query with APM instrumentation.

        Args:
            request: Query request with query text and user ID

        Returns:
            Query response with answer and metadata

        Raises:
            HTTPException: If processing fails
        """
        if pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="Pipeline not initialized - try again in a few seconds"
            )

        try:
            # Track metrics (if available)
            if METRICS_AVAILABLE:
                query_counter.inc()

            # Check cache first
            cached = False
            if request.use_cache:
                cached_result = query_cache.get(request.query, request.user_id)
                if cached_result:
                    cached = True
                    return QueryResponse(
                        **cached_result,
                        cached=True,
                        apm_enabled=apm_manager.is_initialized()
                    )

            # Process query through pipeline
            result = pipeline.process_query(request.query, request.user_id)

            # Cache result
            if request.use_cache:
                query_cache.set(request.query, request.user_id, result)

            return QueryResponse(
                **result,
                cached=False,
                apm_enabled=apm_manager.is_initialized()
            )

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/memory", response_model=MemoryStatsResponse)
    async def get_memory_stats() -> MemoryStatsResponse:
        """
        Get current memory statistics.

        Returns:
            Memory usage statistics in MB
        """
        if memory_profiler is None:
            raise HTTPException(
                status_code=503,
                detail="Memory profiler not initialized"
            )

        try:
            stats = memory_profiler.get_memory_stats()
            return MemoryStatsResponse(**stats)

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/ingest")
    async def ingest_documents(documents: list[str]) -> Dict[str, Any]:
        """
        Ingest documents into memory (for testing memory profiling).

        Args:
            documents: List of document strings to cache

        Returns:
            Ingestion result with memory statistics
        """
        if memory_profiler is None:
            raise HTTPException(
                status_code=503,
                detail="Memory profiler not initialized"
            )

        try:
            # Cache with leak fix (LRU eviction)
            memory_profiler.cache_documents_fixed(documents, max_size=1000)

            # Get updated stats
            stats = memory_profiler.get_memory_stats()

            return {
                "status": "success",
                "documents_ingested": len(documents),
                "memory_stats": stats
            }

        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    if METRICS_AVAILABLE:
        @app.get("/metrics")
        async def metrics():
            """
            Prometheus metrics endpoint.

            Returns:
                Prometheus-formatted metrics
            """
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST
            )

    return app


# Create app instance
app = create_app()


# For local development
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting development server...")
    logger.info("APM Status: %s", "Enabled" if apm_config.is_enabled() else "Disabled")

    # Note: In production, use ddtrace-run wrapper:
    # ddtrace-run uvicorn app:app --host 0.0.0.0 --port 8000

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
