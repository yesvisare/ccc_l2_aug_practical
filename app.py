"""
FastAPI application wrapper for RAGAS Evaluation Framework.
Provides REST API endpoints for evaluation operations.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from datetime import datetime

# Import core functionality
from m8_ragas_eval.ragas_eval import (
    GoldenSetManager,
    RAGASEvaluator,
    DomainAwareEvaluator,
    EvaluationPipeline
)
from m8_ragas_eval.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAGAS Evaluation API",
    description="REST API for systematic RAG system evaluation using RAGAS framework",
    version="1.0.0"
)

# Prometheus metrics (optional)
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    evaluation_counter = Counter('ragas_evaluations_total', 'Total RAGAS evaluations')
    evaluation_duration = Histogram('ragas_evaluation_duration_seconds', 'Evaluation duration')
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False
    logger.warning("Prometheus client not installed - metrics disabled")


# Pydantic models for request/response
class QuestionCreate(BaseModel):
    """Model for creating a golden set question."""
    question: str = Field(..., description="The question text")
    ground_truth: str = Field(..., description="Expected answer")
    contexts: List[str] = Field(..., description="List of relevant context chunks")
    metadata: Optional[Dict] = Field(default=None, description="Optional metadata")


class GoldenSetCreate(BaseModel):
    """Model for creating a golden test set."""
    name: str = Field(..., description="Golden set name")
    version: str = Field(default="v1", description="Version identifier")
    questions: List[QuestionCreate] = Field(..., description="List of questions")


class EvaluationRequest(BaseModel):
    """Model for evaluation request."""
    questions: List[str] = Field(..., description="List of questions")
    generated_answers: List[str] = Field(..., description="Generated answers from RAG system")
    retrieved_contexts: List[List[str]] = Field(..., description="Retrieved contexts per question")
    ground_truths: List[str] = Field(..., description="Ground truth answers")
    model_name: str = Field(default="gpt-3.5-turbo", description="LLM model for judging")
    domain: Optional[str] = Field(default="general", description="Domain for threshold evaluation")


class PipelineRunRequest(BaseModel):
    """Model for running evaluation pipeline."""
    golden_set_name: str = Field(..., description="Name of golden test set")
    golden_set_version: str = Field(default="v1", description="Version of golden test set")
    rag_responses: Dict[str, Dict] = Field(
        ...,
        description="Map of question to {answer, contexts} from RAG system"
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns system status and configuration info.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "openai_configured": Config.has_openai_key(),
            "domain": Config.DOMAIN,
            "batch_size": Config.BATCH_SIZE
        }
    }


# Golden set management endpoints
@app.post("/golden-sets", tags=["Golden Sets"], status_code=201)
async def create_golden_set(golden_set: GoldenSetCreate):
    """
    Create a new golden test set.

    Args:
        golden_set: Golden set data with questions

    Returns:
        Creation status and file path
    """
    try:
        manager = GoldenSetManager()

        # Create questions
        questions = []
        for q in golden_set.questions:
            question = manager.create_question(
                question=q.question,
                ground_truth=q.ground_truth,
                contexts=q.contexts,
                metadata=q.metadata
            )
            questions.append(question)

        # Save golden set
        filepath = manager.save_golden_set(
            questions=questions,
            name=golden_set.name,
            version=golden_set.version
        )

        return {
            "message": "Golden set created successfully",
            "filepath": str(filepath),
            "question_count": len(questions)
        }

    except Exception as e:
        logger.error(f"Failed to create golden set: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/golden-sets/{name}/{version}", tags=["Golden Sets"])
async def get_golden_set(name: str, version: str = "v1"):
    """
    Retrieve a golden test set.

    Args:
        name: Golden set name
        version: Version identifier

    Returns:
        Golden set data
    """
    try:
        manager = GoldenSetManager()
        questions = manager.load_golden_set(name, version)

        return {
            "name": name,
            "version": version,
            "question_count": len(questions),
            "questions": questions
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Golden set not found")
    except Exception as e:
        logger.error(f"Failed to load golden set: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Evaluation endpoints
@app.post("/evaluate", tags=["Evaluation"])
async def evaluate_rag_system(request: EvaluationRequest):
    """
    Evaluate RAG system responses using RAGAS metrics.

    Args:
        request: Evaluation request with questions, answers, and contexts

    Returns:
        RAGAS evaluation scores and report
    """
    # Check API key
    if not Config.has_openai_key():
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "OpenAI API key not configured",
                "message": "Set OPENAI_API_KEY in .env to enable evaluation"
            }
        )

    try:
        # Increment metrics
        if PROMETHEUS_ENABLED:
            evaluation_counter.inc()

        # Validate input lengths
        if not (len(request.questions) == len(request.generated_answers) ==
                len(request.retrieved_contexts) == len(request.ground_truths)):
            raise HTTPException(
                status_code=400,
                detail="All input lists must have the same length"
            )

        # Run RAGAS evaluation
        evaluator = RAGASEvaluator(model_name=request.model_name)

        with evaluation_duration.time() if PROMETHEUS_ENABLED else DummyContext():
            results = evaluator.evaluate_system(
                questions=request.questions,
                generated_answers=request.generated_answers,
                retrieved_contexts=request.retrieved_contexts,
                ground_truths=request.ground_truths,
                skip_if_no_key=False
            )

        # Domain-aware evaluation
        domain_evaluator = DomainAwareEvaluator(domain=request.domain)
        assessment = domain_evaluator.evaluate_with_thresholds(results['scores'])

        # Generate report
        report = evaluator.generate_report(results)

        return {
            "scores": results['scores'],
            "evaluation_time": results['evaluation_time'],
            "question_count": results['question_count'],
            "estimated_cost": results['estimated_cost'],
            "domain_assessment": {
                "domain": request.domain,
                "overall_passed": assessment['overall_passed'],
                "failures": assessment.get('failures', [])
            },
            "report": report
        }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/run", tags=["Pipeline"])
async def run_evaluation_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Run complete evaluation pipeline with regression detection.

    Args:
        request: Pipeline run request with golden set and RAG responses

    Returns:
        Evaluation results with regression analysis
    """
    # Check API key
    if not Config.has_openai_key():
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "OpenAI API key not configured",
                "message": "Set OPENAI_API_KEY in .env to enable evaluation"
            }
        )

    try:
        pipeline = EvaluationPipeline()

        # Create mock RAG query function from provided responses
        def mock_rag_query(question: str) -> Dict:
            if question in request.rag_responses:
                return request.rag_responses[question]
            else:
                raise ValueError(f"No RAG response provided for question: {question}")

        # Run pipeline
        results = pipeline.run_pipeline(
            golden_set_name=request.golden_set_name,
            golden_set_version=request.golden_set_version,
            rag_query_func=mock_rag_query,
            save_results=True
        )

        return {
            "scores": results['results']['scores'],
            "regression_analysis": results['regression_analysis'],
            "evaluation_time": results['results']['evaluation_time'],
            "question_count": results['results']['question_count']
        }

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Metrics endpoint (if Prometheus enabled)
if PROMETHEUS_ENABLED:
    @app.get("/metrics", tags=["Monitoring"])
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Utility endpoints
@app.get("/config", tags=["Configuration"])
async def get_configuration():
    """
    Get current configuration settings.

    Returns:
        Configuration values
    """
    return {
        "openai_model": Config.OPENAI_MODEL,
        "domain": Config.DOMAIN,
        "batch_size": Config.BATCH_SIZE,
        "thresholds": Config.get_domain_thresholds(),
        "directories": {
            "golden_sets": str(Config.GOLDEN_SET_DIR),
            "results": str(Config.RESULTS_DIR),
            "checkpoints": str(Config.CHECKPOINT_DIR)
        }
    }


# Helper context manager for non-Prometheus environments
class DummyContext:
    """Dummy context manager when Prometheus is not enabled."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# Run server with uvicorn
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting RAGAS Evaluation API server...")
    logger.info(f"OpenAI configured: {Config.has_openai_key()}")
    logger.info(f"Prometheus metrics: {'enabled' if PROMETHEUS_ENABLED else 'disabled'}")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
