"""
Module 8.4: Human-in-the-Loop Evaluation - FastAPI Application

Provides REST API endpoints for:
- Collecting user feedback
- Selecting queries for annotation
- Measuring inter-annotator agreement
- Exporting to Label Studio
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import numpy as np
import logging

from l2_m8_hitl_evaluation import (
    FeedbackCollector,
    Feedback,
    ActiveLearningSelector,
    InterAnnotatorAgreement,
    FeedbackLoopManager,
    export_to_label_studio
)
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Module 8.4: Human-in-the-Loop Evaluation API",
    description="REST API for HITL evaluation in RAG systems",
    version="1.0.0"
)

# Initialize components
feedback_collector = FeedbackCollector(db_path=Config.DB_PATH)
active_learning = ActiveLearningSelector(
    uncertainty_weight=Config.UNCERTAINTY_WEIGHT,
    negative_feedback_boost=Config.NEGATIVE_FEEDBACK_BOOST
)
iaa_calculator = InterAnnotatorAgreement()
loop_manager = FeedbackLoopManager()


# ========== Request/Response Models ==========

class FeedbackRequest(BaseModel):
    """Request model for submitting user feedback."""
    query_id: str = Field(..., description="Unique query identifier")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    feedback_type: str = Field(..., description="Type: thumbs_up, thumbs_down, rating")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Star rating 1-5")
    comment: Optional[str] = Field(None, description="Optional text comment")


class QueryForSelection(BaseModel):
    """Query model for active learning selection."""
    query_id: str
    query_text: str
    response_text: str
    sources: List[str] = []
    confidence: float = Field(ge=0.0, le=1.0)
    has_negative_feedback: bool = False
    embedding: List[float]


class SelectionRequest(BaseModel):
    """Request model for active learning selection."""
    queries: List[QueryForSelection]
    n_select: int = Field(50, ge=1, le=500, description="Number of queries to select")
    n_clusters: int = Field(10, ge=1, le=50, description="Number of diversity clusters")


class IAARequest(BaseModel):
    """Request model for inter-annotator agreement calculation."""
    annotator_a: List[int]
    annotator_b: List[int]
    metric: str = Field("kappa", description="Metric: kappa or alpha")


class AnnotationBatch(BaseModel):
    """Batch of annotations for aggregation."""
    query_id: str
    annotator_id: str
    factual_correctness: bool
    helpfulness: int = Field(ge=1, le=5)
    needs_improvement: bool = False


# ========== API Endpoints ==========

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "module": "m8.4_hitl_evaluation", "timestamp": datetime.now().isoformat()}


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for a query-response pair.

    Returns:
        Success confirmation or error message
    """
    try:
        feedback = Feedback(
            query_id=request.query_id,
            user_id=request.user_id,
            feedback_type=request.feedback_type,
            rating=request.rating,
            comment=request.comment,
            timestamp=datetime.now().isoformat(),
            processed=False
        )

        success = feedback_collector.add_feedback(feedback)

        if success:
            return {
                "status": "success",
                "message": f"Feedback stored for query {request.query_id}",
                "query_id": request.query_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store feedback"
            )

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/feedback/unprocessed")
async def get_unprocessed_feedback(limit: int = 100):
    """
    Retrieve unprocessed feedback entries.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of unprocessed feedback
    """
    try:
        feedback_list = feedback_collector.get_unprocessed_feedback(limit=limit)
        return {
            "status": "success",
            "count": len(feedback_list),
            "feedback": feedback_list
        }
    except Exception as e:
        logger.error(f"Error retrieving feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/select-for-annotation")
async def select_for_annotation(request: SelectionRequest):
    """
    Select queries for human annotation using active learning.

    Returns:
        List of selected queries prioritized by uncertainty and diversity
    """
    if not Config.is_label_studio_configured():
        logger.warning("Label Studio not configured - returning selection only")

    try:
        # Convert queries to dict format
        queries = [
            {
                "query_id": q.query_id,
                "query_text": q.query_text,
                "response_text": q.response_text,
                "sources": q.sources,
                "confidence": q.confidence,
                "has_negative_feedback": q.has_negative_feedback
            }
            for q in request.queries
        ]

        # Extract embeddings
        embeddings = np.array([q.embedding for q in request.queries])

        # Select queries
        selected_tasks = active_learning.select_for_annotation(
            queries=queries,
            embeddings=embeddings,
            n_select=request.n_select,
            n_clusters=request.n_clusters
        )

        # Convert to response format
        selected = [
            {
                "query_id": task.query_id,
                "query_text": task.query_text,
                "response_text": task.response_text,
                "sources": task.sources,
                "uncertainty_score": task.uncertainty_score,
                "priority_score": task.priority_score
            }
            for task in selected_tasks
        ]

        return {
            "status": "success",
            "n_selected": len(selected),
            "selected_queries": selected,
            "label_studio_configured": Config.is_label_studio_configured()
        }

    except Exception as e:
        logger.error(f"Error in active learning selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/export-label-studio")
async def export_label_studio(request: SelectionRequest, output_path: str = "label_studio_tasks.json"):
    """
    Export selected queries to Label Studio JSON format.

    Returns:
        Export status and file path
    """
    try:
        # Convert queries
        queries = [
            {
                "query_id": q.query_id,
                "query_text": q.query_text,
                "response_text": q.response_text,
                "sources": q.sources,
                "confidence": q.confidence,
                "has_negative_feedback": q.has_negative_feedback
            }
            for q in request.queries
        ]

        embeddings = np.array([q.embedding for q in request.queries])

        # Select tasks
        selected_tasks = active_learning.select_for_annotation(
            queries=queries,
            embeddings=embeddings,
            n_select=request.n_select,
            n_clusters=request.n_clusters
        )

        # Export
        success = export_to_label_studio(selected_tasks, output_path)

        if success:
            return {
                "status": "success",
                "message": f"Exported {len(selected_tasks)} tasks to Label Studio format",
                "output_path": output_path,
                "n_tasks": len(selected_tasks)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Export failed"
            )

    except Exception as e:
        logger.error(f"Error exporting to Label Studio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/iaa/calculate")
async def calculate_iaa(request: IAARequest):
    """
    Calculate inter-annotator agreement (IAA).

    Supports:
    - Cohen's Kappa (for 2 annotators)
    - Krippendorff's Alpha (for multiple annotators)

    Returns:
        IAA score and interpretation
    """
    try:
        if request.metric.lower() == "kappa":
            if len(request.annotator_a) != len(request.annotator_b):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Annotator lists must have same length"
                )

            score = iaa_calculator.cohens_kappa(request.annotator_a, request.annotator_b)
            metric_name = "Cohen's Kappa"

        elif request.metric.lower() == "alpha":
            annotations = [request.annotator_a, request.annotator_b]
            score = iaa_calculator.krippendorffs_alpha(annotations)
            metric_name = "Krippendorff's Alpha"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Metric must be 'kappa' or 'alpha'"
            )

        # Interpret score
        if score >= Config.MIN_IAA_THRESHOLD:
            interpretation = "Good agreement (≥0.70)"
            alert = False
        elif score >= 0.40:
            interpretation = "Moderate agreement (0.40-0.69)"
            alert = True
        else:
            interpretation = "Poor agreement (<0.40)"
            alert = True

        return {
            "status": "success",
            "metric": metric_name,
            "score": round(score, 3),
            "interpretation": interpretation,
            "threshold": Config.MIN_IAA_THRESHOLD,
            "alert": alert
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating IAA: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/annotations/aggregate")
async def aggregate_annotations(annotations: List[AnnotationBatch]):
    """
    Aggregate annotations from multiple annotators.

    Returns:
        Aggregated results with majority votes and confidence
    """
    try:
        annotation_dicts = [
            {
                "query_id": ann.query_id,
                "annotator_id": ann.annotator_id,
                "factual_correctness": ann.factual_correctness,
                "helpfulness": ann.helpfulness,
                "needs_improvement": ann.needs_improvement
            }
            for ann in annotations
        ]

        # Group by query_id
        query_groups = {}
        for ann in annotation_dicts:
            qid = ann['query_id']
            if qid not in query_groups:
                query_groups[qid] = []
            query_groups[qid].append(ann)

        # Aggregate each group
        results = []
        for query_id, group in query_groups.items():
            aggregated = loop_manager.aggregate_annotations(group)
            results.append(aggregated)

        return {
            "status": "success",
            "n_queries": len(results),
            "aggregated_results": results
        }

    except Exception as e:
        logger.error(f"Error aggregating annotations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/feedback-loop/extract-training")
async def extract_training_examples(
    annotations: List[AnnotationBatch],
    min_confidence: float = 0.7
):
    """
    Extract high-confidence examples for retraining.

    Args:
        annotations: List of annotations
        min_confidence: Minimum confidence threshold

    Returns:
        Training examples for model improvement
    """
    try:
        # Aggregate first
        annotation_dicts = [
            {
                "query_id": ann.query_id,
                "annotator_id": ann.annotator_id,
                "factual_correctness": ann.factual_correctness,
                "helpfulness": ann.helpfulness,
                "needs_improvement": ann.needs_improvement
            }
            for ann in annotations
        ]

        query_groups = {}
        for ann in annotation_dicts:
            qid = ann['query_id']
            if qid not in query_groups:
                query_groups[qid] = []
            query_groups[qid].append(ann)

        aggregated = []
        for query_id, group in query_groups.items():
            agg = loop_manager.aggregate_annotations(group)
            aggregated.append(agg)

        # Extract training examples
        training_examples = loop_manager.extract_training_examples(
            aggregated,
            min_confidence=min_confidence
        )

        return {
            "status": "success",
            "n_examples": len(training_examples),
            "min_confidence": min_confidence,
            "training_examples": training_examples
        }

    except Exception as e:
        logger.error(f"Error extracting training examples: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/metrics")
async def get_metrics():
    """
    Get system metrics (optional - requires prometheus-client).

    Returns:
        Basic metrics about feedback and annotations
    """
    if not Config.ENABLE_METRICS:
        return {
            "status": "disabled",
            "message": "Metrics disabled. Set ENABLE_METRICS=true to enable."
        }

    try:
        unprocessed = feedback_collector.get_unprocessed_feedback(limit=10000)

        return {
            "status": "ok",
            "metrics": {
                "unprocessed_feedback_count": len(unprocessed),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        return {"status": "error", "message": str(e)}


# ========== Main Entry Point ==========

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting HITL Evaluation API on {Config.API_HOST}:{Config.API_PORT}")
    logger.info(f"Label Studio configured: {Config.is_label_studio_configured()}")

    uvicorn.run(
        "app:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True,
        log_level="info"
    )
