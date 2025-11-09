"""
FastAPI Application for Module 8.2: A/B Testing for RAG Improvements

Provides REST API endpoints for A/B testing operations.
Run with: python app.py or uvicorn app:app --reload
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Import our module
from m8_ab_testing_rag.ab_testing import (
    ExperimentConfig,
    ExperimentManager,
    TrafficSplitter,
    ABTestingRAGPipeline,
    StatisticalAnalyzer,
    RolloutController,
    calculate_required_sample_size
)
import m8_ab_testing_rag.config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="A/B Testing for RAG Improvements",
    description="REST API for managing and analyzing A/B tests on RAG systems",
    version="1.0.0"
)

# Initialize components (without DB for demo)
db_conn = config.get_database_connection()
experiment_manager = ExperimentManager(db_conn)
traffic_splitter = TrafficSplitter(db_conn)
rag_pipeline = ABTestingRAGPipeline(
    base_retriever=None,  # Would connect to real retriever in production
    base_llm=None,  # Would connect to real LLM in production
    ragas_evaluator=None,  # Would connect to real RAGAS in production
    db_connection=db_conn
)
statistical_analyzer = StatisticalAnalyzer(db_conn)
rollout_controller = RolloutController(db_conn)


# Request/Response Models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database_connected: bool
    api_keys_configured: bool


class ExperimentRequest(BaseModel):
    experiment_id: str = Field(..., description="Unique experiment identifier")
    name: str = Field(..., description="Human-readable experiment name")
    description: str = Field("", description="Experiment description")
    control_config: Dict[str, Any] = Field(..., description="Control variant configuration")
    treatment_config: Dict[str, Any] = Field(..., description="Treatment variant configuration")
    traffic_split: float = Field(0.5, ge=0.0, le=1.0, description="Percentage for treatment (0.5 = 50%)")


class ExperimentResponse(BaseModel):
    experiment_id: str
    status: str
    message: str


class QueryRequest(BaseModel):
    question: str = Field(..., description="User's question")
    user_id: str = Field(..., description="User identifier for consistent assignment")
    query_id: Optional[str] = Field(None, description="Optional query ID (auto-generated if not provided)")


class QueryResponse(BaseModel):
    response: str
    contexts: list
    metrics: Dict[str, float]
    variant: str
    experiment_id: Optional[str]
    latency_ms: int


class AnalysisRequest(BaseModel):
    experiment_id: str
    metric: str = Field("faithfulness", description="Metric to analyze")


class AnalysisResponse(BaseModel):
    experiment_id: str
    control_mean: float
    treatment_mean: float
    difference: float
    percent_change: float
    p_value: float
    is_significant: bool
    confidence_interval_95: tuple
    sample_size_control: int
    sample_size_treatment: int
    winner: str
    recommendation: str


# Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        database_connected=db_conn is not None,
        api_keys_configured=config.OPENAI_API_KEY is not None or config.ANTHROPIC_API_KEY is not None
    )


@app.post("/experiment", response_model=ExperimentResponse)
async def create_experiment(request: ExperimentRequest):
    """
    Create a new A/B testing experiment.

    Args:
        request: Experiment configuration

    Returns:
        Experiment creation status
    """
    try:
        exp_config = ExperimentConfig(
            experiment_id=request.experiment_id,
            name=request.name,
            description=request.description,
            control_config=request.control_config,
            treatment_config=request.treatment_config,
            traffic_split=request.traffic_split
        )

        exp_id = experiment_manager.create_experiment(exp_config)

        logger.info(f"Created experiment: {exp_id}")

        return ExperimentResponse(
            experiment_id=exp_id,
            status="created",
            message=f"Experiment '{request.name}' created successfully"
        )

    except Exception as e:
        logger.error(f"Failed to create experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments", response_model=list)
async def list_experiments():
    """
    List all active experiments.

    Returns:
        List of active experiment configurations
    """
    try:
        experiments = experiment_manager.get_active_experiments()

        return [
            {
                "experiment_id": exp.experiment_id,
                "name": exp.name,
                "description": exp.description,
                "traffic_split": exp.traffic_split,
                "status": exp.status
            }
            for exp in experiments
        ]

    except Exception as e:
        logger.error(f"Failed to list experiments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """
    Execute RAG query with A/B testing.

    If no API keys configured, returns simulated results with a notice.

    Args:
        request: Query details

    Returns:
        Query response with variant and metrics
    """
    try:
        # Auto-generate query_id if not provided
        query_id = request.query_id or f"query_{datetime.now().timestamp()}"

        # Check if we're in demo mode
        if not config.OPENAI_API_KEY and not config.ANTHROPIC_API_KEY:
            logger.warning("⚠️ No API keys configured, running in demo mode")

        result = rag_pipeline.query(
            question=request.question,
            user_id=request.user_id,
            query_id=query_id
        )

        return QueryResponse(**result)

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_experiment(request: AnalysisRequest):
    """
    Analyze experiment results for statistical significance.

    Args:
        request: Analysis parameters

    Returns:
        Statistical analysis results
    """
    try:
        # Get in-memory data if no database
        in_memory_data = rag_pipeline._results if not db_conn else None

        results = statistical_analyzer.analyze_experiment(
            experiment_id=request.experiment_id,
            metric=request.metric,
            in_memory_data=in_memory_data
        )

        logger.info(f"Analysis complete: {results.winner}, p={results.p_value:.4f}")

        return AnalysisResponse(
            experiment_id=results.experiment_id,
            control_mean=results.control_mean,
            treatment_mean=results.treatment_mean,
            difference=results.difference,
            percent_change=results.percent_change,
            p_value=results.p_value,
            is_significant=results.is_significant,
            confidence_interval_95=results.confidence_interval_95,
            sample_size_control=results.sample_size_control,
            sample_size_treatment=results.sample_size_treatment,
            winner=results.winner,
            recommendation=results.recommendation
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate-sample-size")
async def calculate_sample_size(
    effect_size: float = 0.03,
    alpha: float = 0.05,
    power: float = 0.8
):
    """
    Calculate required sample size for experiment.

    Args:
        effect_size: Expected improvement (e.g., 0.03 for 3%)
        alpha: Significance level (default 0.05)
        power: Statistical power (default 0.8)

    Returns:
        Required sample size per variant and estimated runtime
    """
    try:
        required_n = calculate_required_sample_size(
            effect_size=effect_size,
            alpha=alpha,
            power=power
        )

        # Estimate runtime at different traffic levels
        queries_per_day_options = [100, 500, 1000, 5000]
        runtime_estimates = {
            f"{qpd}_queries_per_day": round((required_n * 2) / qpd, 1)
            for qpd in queries_per_day_options
        }

        return {
            "required_samples_per_variant": required_n,
            "total_samples_needed": required_n * 2,
            "parameters": {
                "effect_size": effect_size,
                "alpha": alpha,
                "power": power
            },
            "estimated_runtime_days": runtime_estimates
        }

    except Exception as e:
        logger.error(f"Sample size calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/experiment/{experiment_id}/stop")
async def stop_experiment(experiment_id: str, winner: str):
    """
    Stop an experiment and record the winner.

    Args:
        experiment_id: Experiment to stop
        winner: 'control', 'treatment', or 'inconclusive'

    Returns:
        Status message
    """
    try:
        experiment_manager.stop_experiment(experiment_id, winner)

        logger.info(f"Stopped experiment {experiment_id}, winner: {winner}")

        return {
            "status": "stopped",
            "experiment_id": experiment_id,
            "winner": winner,
            "message": f"Experiment stopped successfully"
        }

    except Exception as e:
        logger.error(f"Failed to stop experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Optional: Prometheus metrics endpoint
if config.ENABLE_METRICS:
    try:
        from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response

        # Define metrics
        query_counter = Counter('rag_queries_total', 'Total RAG queries', ['variant', 'experiment_id'])
        query_latency = Histogram('rag_query_latency_seconds', 'RAG query latency', ['variant'])

        @app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

        logger.info("Prometheus metrics enabled on /metrics")
    except ImportError:
        logger.warning("prometheus_client not installed, metrics disabled")


# Run server
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting A/B Testing for RAG Improvements API")
    logger.info("=" * 60)
    logger.info(f"Host: {config.APP_HOST}")
    logger.info(f"Port: {config.APP_PORT}")
    logger.info(f"Database: {'✅ Connected' if db_conn else '⚠️  In-memory mode'}")
    logger.info(f"API Keys: {'✅ Configured' if config.OPENAI_API_KEY or config.ANTHROPIC_API_KEY else '⚠️  Demo mode'}")
    logger.info("=" * 60)

    uvicorn.run(
        "app:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    )
