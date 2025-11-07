"""
FastAPI Application with OpenTelemetry Distributed Tracing

Module entrypoint providing HTTP endpoints for RAG queries with full tracing.
Demonstrates auto-instrumentation with FastAPIInstrumentor.

Endpoints:
- GET /health: Health check
- POST /query: RAG query with tracing
- GET /trace/{trace_id}: Get trace context info
- GET /metrics: Prometheus metrics (optional)

Graceful degradation: Returns 200 with skipped=true if Jaeger unavailable.
"""

import logging
import time
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Import core module and config
from l2_m7_distributed_tracing_opentelemetry import (
    setup_tracing,
    process_rag_query,
    get_trace_context,
    traced_operation
)
from config import tracing_config, app_config, validate_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=app_config.APP_NAME,
    version=app_config.APP_VERSION,
    description="RAG system with OpenTelemetry distributed tracing demonstration"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize tracer
tracer = None
tracing_available = False

try:
    if tracing_config.TRACING_ENABLED:
        tracer = setup_tracing(
            service_name=tracing_config.SERVICE_NAME,
            environment=tracing_config.ENVIRONMENT,
            version=tracing_config.SERVICE_VERSION,
            otlp_endpoint=tracing_config.OTLP_ENDPOINT,
            sampling_rate=tracing_config.SAMPLING_RATE,
            max_queue_size=tracing_config.MAX_QUEUE_SIZE,
            max_export_batch_size=tracing_config.MAX_EXPORT_BATCH_SIZE,
            schedule_delay_millis=tracing_config.SCHEDULE_DELAY_MILLIS
        )

        # Auto-instrument FastAPI
        # This creates parent spans for all HTTP requests automatically
        FastAPIInstrumentor.instrument_app(app)

        tracing_available = True
        logger.info("✅ OpenTelemetry tracing initialized and FastAPI instrumented")
    else:
        logger.warning("⚠️ Tracing disabled in configuration")
except Exception as e:
    logger.error(f"❌ Failed to initialize tracing: {e}")
    logger.info("Application will continue without tracing (graceful degradation)")


# Request/Response Models
class QueryRequest(BaseModel):
    """RAG query request model."""
    question: str = Field(..., description="User question for RAG pipeline", min_length=1)
    top_k: Optional[int] = Field(
        default=None,
        description="Number of documents to retrieve",
        ge=1,
        le=100
    )
    top_n: Optional[int] = Field(
        default=None,
        description="Number of documents to rerank",
        ge=1,
        le=50
    )
    model: Optional[str] = Field(
        default=None,
        description="LLM model name (e.g., gpt-4, gpt-3.5-turbo)"
    )


class QueryResponse(BaseModel):
    """RAG query response model."""
    question: str
    response: str
    total_time_ms: float
    retrieved_count: int
    reranked_count: int
    tokens: int
    cost_usd: float
    model: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    jaeger_ui_url: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    tracing_enabled: bool
    tracing_available: bool
    jaeger_reachable: Optional[bool] = None
    config: Dict[str, Any]


class TraceContextResponse(BaseModel):
    """Trace context information."""
    trace_id: Optional[str]
    span_id: Optional[str]
    jaeger_ui_url: Optional[str]


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns service status and tracing configuration.
    Validates Jaeger connectivity.
    """
    validation = validate_config()

    return HealthResponse(
        status="ok",
        tracing_enabled=tracing_config.TRACING_ENABLED,
        tracing_available=tracing_available,
        jaeger_reachable=validation.get("jaeger_reachable"),
        config=tracing_config.to_dict()
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Process RAG query with distributed tracing.

    This endpoint demonstrates the full RAG pipeline with tracing:
    1. FastAPIInstrumentor creates parent HTTP request span automatically
    2. process_rag_query creates nested spans for retrieval, reranking, generation
    3. Trace context is returned for correlation with Jaeger UI

    Returns:
        QueryResponse with answer, timing, and trace context

    Graceful degradation:
        If Jaeger unavailable, still processes query but returns skipped=true
    """
    if not tracing_available:
        # Graceful degradation: process without tracing
        logger.warning("Processing query without tracing (Jaeger unavailable)")

    # Use config defaults if not specified
    top_k = request.top_k or app_config.DEFAULT_TOP_K
    top_n = request.top_n or app_config.DEFAULT_TOP_N
    model = request.model or app_config.DEFAULT_MODEL

    try:
        # Process RAG query with tracing
        result = process_rag_query(
            tracer=tracer,
            question=request.question,
            top_k=top_k,
            top_n=top_n,
            model=model
        )

        # Get trace context for correlation
        trace_ctx = get_trace_context()

        # Build Jaeger UI URL for this trace
        jaeger_url = None
        if trace_ctx["trace_id"]:
            jaeger_url = (
                f"{tracing_config.JAEGER_UI_URL}/trace/{trace_ctx['trace_id']}"
            )

        return QueryResponse(
            question=result["question"],
            response=result["response"],
            total_time_ms=result["total_time_ms"],
            retrieved_count=result["retrieved_count"],
            reranked_count=result["reranked_count"],
            tokens=result["tokens"],
            cost_usd=result["cost_usd"],
            model=result["model"],
            trace_id=trace_ctx["trace_id"],
            span_id=trace_ctx["span_id"],
            jaeger_ui_url=jaeger_url
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trace/current", response_model=TraceContextResponse)
async def get_current_trace_context():
    """
    Get current trace context.

    Useful for debugging and correlation with logs.
    Returns trace_id and span_id for the current request.
    """
    trace_ctx = get_trace_context()

    jaeger_url = None
    if trace_ctx["trace_id"]:
        jaeger_url = (
            f"{tracing_config.JAEGER_UI_URL}/trace/{trace_ctx['trace_id']}"
        )

    return TraceContextResponse(
        trace_id=trace_ctx["trace_id"],
        span_id=trace_ctx["span_id"],
        jaeger_ui_url=jaeger_url
    )


@app.get("/config")
async def get_config():
    """
    Get current tracing configuration.

    Useful for debugging configuration issues.
    """
    return {
        "tracing": tracing_config.to_dict(),
        "app": {
            "name": app_config.APP_NAME,
            "version": app_config.APP_VERSION,
            "host": app_config.HOST,
            "port": app_config.PORT
        },
        "validation": validate_config()
    }


# Optional: Prometheus metrics endpoint
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    # Define metrics
    query_counter = Counter(
        'rag_queries_total',
        'Total number of RAG queries',
        ['model', 'status']
    )

    query_duration = Histogram(
        'rag_query_duration_seconds',
        'RAG query duration',
        ['model'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    )

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info("✅ Prometheus metrics endpoint enabled at /metrics")

except ImportError:
    logger.info("⚠️ prometheus-client not installed, /metrics endpoint disabled")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info(f"🚀 Starting {app_config.APP_NAME} v{app_config.APP_VERSION}")
    logger.info(f"Environment: {tracing_config.ENVIRONMENT}")
    logger.info(f"Tracing enabled: {tracing_available}")

    if tracing_available:
        logger.info(f"OTLP endpoint: {tracing_config.OTLP_ENDPOINT}")
        logger.info(f"Sampling rate: {tracing_config.SAMPLING_RATE * 100}%")
        logger.info(f"Jaeger UI: {tracing_config.JAEGER_UI_URL}")
    else:
        logger.warning("⚠️ Tracing not available - check Jaeger connection")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application")


# CLI runner
if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print(f"{app_config.APP_NAME} v{app_config.APP_VERSION}")
    print("=" * 70)
    print("\nStarting FastAPI server with OpenTelemetry tracing...")
    print(f"\nEndpoints:")
    print(f"  • Health:  http://{app_config.HOST}:{app_config.PORT}/health")
    print(f"  • Query:   http://{app_config.HOST}:{app_config.PORT}/query")
    print(f"  • Docs:    http://{app_config.HOST}:{app_config.PORT}/docs")
    print(f"  • Config:  http://{app_config.HOST}:{app_config.PORT}/config")

    if tracing_available:
        print(f"\nTracing:")
        print(f"  • Jaeger UI: {tracing_config.JAEGER_UI_URL}")
        print(f"  • Sampling:  {tracing_config.SAMPLING_RATE * 100}%")
    else:
        print("\n⚠️  Tracing unavailable - start Jaeger:")
        print("   docker run -d --name jaeger \\")
        print("     -e COLLECTOR_OTLP_ENABLED=true \\")
        print("     -p 16686:16686 -p 4317:4317 -p 4318:4318 \\")
        print("     jaegertracing/all-in-one:1.51")

    print("\n" + "=" * 70 + "\n")

    uvicorn.run(
        app,
        host=app_config.HOST,
        port=app_config.PORT,
        log_level="info"
    )
