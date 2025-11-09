"""
FastAPI application for Module 8.3: Regression Testing & CI/CD

Provides REST API endpoints for:
- Health checks
- Running regression tests
- DVC version management
- Cost estimation
- Decision helper

No business logic here - all functionality imported from reg_test.py
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path

# Import core module
import m8_regression_cicd.regression as reg_test
import m8_regression_cicd.config as config

# Optional: Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    PROMETHEUS_AVAILABLE = True

    # Define metrics
    request_counter = Counter('regression_test_requests_total', 'Total regression test requests')
    test_duration = Histogram('regression_test_duration_seconds', 'Regression test duration')
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Module 8.3: Regression Testing & CI/CD",
    description="REST API for RAG regression testing and CI/CD operations",
    version="1.0.0"
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    services_available: Dict[str, bool]


class RegressionTestRequest(BaseModel):
    """Request model for regression testing."""
    test_data_path: Optional[str] = Field(
        default="test_data/example_data.json",
        description="Path to test data JSON file"
    )
    use_subset: bool = Field(
        default=True,
        description="Use 50-question subset (True) or full set (False)"
    )


class RegressionTestResponse(BaseModel):
    """Response model for regression testing."""
    status: str
    metrics: Optional[Dict[str, float]] = None
    passes_thresholds: bool
    failures: List[str]
    skipped: bool = False
    reason: Optional[str] = None


class CostEstimateRequest(BaseModel):
    """Request model for cost estimation."""
    deploys_per_month: int = Field(..., ge=1, le=1000)
    team_size: int = Field(..., ge=1, le=100)


class CostEstimateResponse(BaseModel):
    """Response model for cost estimation."""
    deploys_per_month: int
    team_size: int
    github_actions: float
    storage: float
    api_testing: float
    total: float


class DecisionRequest(BaseModel):
    """Request model for CI/CD decision helper."""
    deploys_per_month: int = Field(..., ge=1, le=1000)
    team_size: int = Field(..., ge=1, le=100)
    budget_per_month: float = Field(..., ge=0)
    has_pmf: bool = Field(default=True)


class DecisionResponse(BaseModel):
    """Response model for CI/CD decision helper."""
    should_use_cicd: bool
    reason: str
    estimated_cost: float


class VersionListResponse(BaseModel):
    """Response model for listing versions."""
    versions: List[str]
    count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns service status and availability of external dependencies.
    """
    validation = config.validate_config()

    return HealthResponse(
        status="ok",
        services_available=validation
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "module": "8.3: Regression Testing & CI/CD",
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "run_tests": "POST /tests/run",
            "estimate_costs": "POST /costs/estimate",
            "decision_helper": "POST /decision",
            "list_versions": "GET /versions",
            "metrics": "GET /metrics (if prometheus-client installed)"
        }
    }


@app.post("/tests/run", response_model=RegressionTestResponse)
async def run_regression_tests(request: RegressionTestRequest):
    """
    Run regression test suite.

    Tests faithfulness, relevancy, precision, latency, and cost metrics.
    Returns whether tests pass configured thresholds.

    If OpenAI API key is not configured, returns skipped response.
    """
    if PROMETHEUS_AVAILABLE:
        request_counter.inc()

    # Check if services are available
    if not config.has_required_services():
        logger.warning("⚠️ Skipping regression tests (no API keys/services)")
        return RegressionTestResponse(
            status="skipped",
            passes_thresholds=False,
            failures=[],
            skipped=True,
            reason="OpenAI API key not configured"
        )

    try:
        # Load test data
        test_data_path = Path(request.test_data_path)
        if not test_data_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test data file not found: {request.test_data_path}"
            )

        import json
        with open(test_data_path, 'r') as f:
            data = json.load(f)
            test_questions = data['test_questions']

        # Create test suite
        test_suite = reg_test.RegressionTestSuite(
            test_questions,
            use_subset=request.use_subset
        )

        # Mock RAG pipeline (replace with actual pipeline in production)
        class MockPipeline:
            def query(self, question):
                return {
                    'answer': f'Mock answer for: {question}',
                    'contexts': ['Mock context 1', 'Mock context 2']
                }

        # Run tests
        logger.info("Running regression tests...")
        metrics = test_suite.run_quality_tests(MockPipeline())

        # Check thresholds
        passes, failures = metrics.passes_thresholds()

        return RegressionTestResponse(
            status="completed",
            metrics={
                'faithfulness': metrics.faithfulness,
                'answer_relevancy': metrics.answer_relevancy,
                'context_precision': metrics.context_precision,
                'p95_latency_ms': metrics.p95_latency_ms,
                'cost_per_query': metrics.cost_per_query
            },
            passes_thresholds=passes,
            failures=failures
        )

    except Exception as e:
        logger.error(f"Regression test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test execution failed: {str(e)}"
        )


@app.post("/costs/estimate", response_model=CostEstimateResponse)
async def estimate_costs(request: CostEstimateRequest):
    """
    Estimate CI/CD costs based on deployment frequency and team size.

    Returns breakdown of GitHub Actions, S3 storage, and API testing costs.
    """
    try:
        costs = reg_test.estimate_cicd_costs(
            request.deploys_per_month,
            request.team_size
        )

        return CostEstimateResponse(
            deploys_per_month=request.deploys_per_month,
            team_size=request.team_size,
            github_actions=costs['github_actions'],
            storage=costs['storage'],
            api_testing=costs['api_testing'],
            total=costs['total']
        )

    except Exception as e:
        logger.error(f"Cost estimation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost estimation failed: {str(e)}"
        )


@app.post("/decision", response_model=DecisionResponse)
async def decision_helper(request: DecisionRequest):
    """
    Determine if CI/CD is appropriate for given parameters.

    Uses decision framework from script to provide recommendation.
    """
    try:
        should_use, reason = reg_test.should_use_cicd(
            request.deploys_per_month,
            request.team_size,
            request.budget_per_month,
            request.has_pmf
        )

        # Estimate costs
        costs = reg_test.estimate_cicd_costs(
            request.deploys_per_month,
            request.team_size
        )

        return DecisionResponse(
            should_use_cicd=should_use,
            reason=reason,
            estimated_cost=costs['total']
        )

    except Exception as e:
        logger.error(f"Decision helper failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision helper failed: {str(e)}"
        )


@app.get("/versions", response_model=VersionListResponse)
async def list_versions():
    """
    List available DVC model versions.

    Returns Git tags that represent versioned model snapshots.
    """
    try:
        manager = reg_test.DVCVersionManager()
        versions = manager.list_versions()

        return VersionListResponse(
            versions=versions,
            count=len(versions)
        )

    except Exception as e:
        logger.error(f"Version listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Version listing failed: {str(e)}"
        )


@app.get("/config")
async def get_configuration():
    """
    Get current configuration information.

    Returns thresholds, test settings, and service availability.
    """
    return config.get_config_info()


# ============================================================================
# OPTIONAL: PROMETHEUS METRICS ENDPOINT
# ============================================================================

if PROMETHEUS_AVAILABLE:
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


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("=" * 70)
    logger.info("Module 8.3: Regression Testing & CI/CD - API Server")
    logger.info("=" * 70)
    logger.info(f"Faithfulness threshold: ≥{config.FAITHFULNESS_THRESHOLD}")
    logger.info(f"Relevancy threshold: ≥{config.ANSWER_RELEVANCY_THRESHOLD}")
    logger.info(f"Precision threshold: ≥{config.CONTEXT_PRECISION_THRESHOLD}")
    logger.info(f"P95 latency threshold: ≤{config.P95_LATENCY_THRESHOLD_MS}ms")
    logger.info(f"Cost threshold: ≤${config.COST_PER_QUERY_THRESHOLD}")

    validation = config.validate_config()
    available_services = [k for k, v in validation.items() if v]
    logger.info(f"Available services: {', '.join(available_services) if available_services else 'none'}")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    logger.info("Shutting down API server...")


# ============================================================================
# LOCAL DEVELOPMENT
# ============================================================================

if __name__ == "__main__":
    """Run server locally for development."""
    import uvicorn

    print("Starting development server...")
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
