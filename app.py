"""
FastAPI application for M5.3: Data Quality & Validation

Provides REST API endpoints for quality scoring, duplicate detection, and drift monitoring.
No business logic in this file - imports and calls functions from l2_m3_dataquality_validation.py
"""

import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import config
from l2_m3_dataquality_validation import (
    ChunkMetadata,
    ChunkQualityScorer,
    DataDriftDetector,
    DuplicateDetector,
    filter_low_quality_chunks,
    remove_duplicates,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M5.3: Data Quality & Validation API",
    description="Production-ready data quality validation for RAG systems",
    version="1.0.0"
)

# Optional Prometheus metrics
if config.ENABLE_PROMETHEUS:
    try:
        from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response

        chunks_processed = Counter(
            'chunks_processed_total',
            'Total chunks processed',
            ['status']
        )
        quality_score_hist = Histogram(
            'chunk_quality_score',
            'Distribution of quality scores'
        )

        @app.get("/metrics")
        def metrics():
            """Prometheus metrics endpoint."""
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

        logger.info("Prometheus metrics enabled at /metrics")
    except ImportError:
        logger.warning("prometheus-client not installed, /metrics disabled")
        config.ENABLE_PROMETHEUS = False


# Request/Response Models
class ChunkMetadataModel(BaseModel):
    """Chunk metadata model."""
    source: Optional[str] = None
    date: Optional[str] = None
    section: Optional[str] = None
    chunk_id: Optional[str] = None


class ChunkInput(BaseModel):
    """Input model for a single chunk."""
    chunk_id: str
    text: str
    metadata: Optional[ChunkMetadataModel] = None


class QualityScoreRequest(BaseModel):
    """Request model for quality scoring."""
    chunks: List[ChunkInput]
    min_score: float = Field(default=70.0, ge=0, le=100)
    optimal_length_min: int = Field(default=200, ge=50)
    optimal_length_max: int = Field(default=800, ge=100)


class QualityScoreResponse(BaseModel):
    """Response model for quality scoring."""
    total_chunks: int
    passed_chunks: int
    failed_chunks: int
    pass_rate: float
    scores: List[Dict]


class DuplicateDetectionRequest(BaseModel):
    """Request model for duplicate detection."""
    chunks: List[ChunkInput]
    threshold: float = Field(default=0.85, ge=0, le=1)


class DuplicateDetectionResponse(BaseModel):
    """Response model for duplicate detection."""
    total_chunks: int
    unique_chunks: int
    duplicates_found: int
    dedup_rate: float
    unique_chunk_ids: List[str]
    duplicate_info: List[Dict]


class DriftDetectionRequest(BaseModel):
    """Request model for drift detection."""
    quality_scores: List[float]
    chunk_lengths: List[int]
    information_density: List[float]
    significance_level: float = Field(default=0.05, ge=0.01, le=0.1)
    drift_threshold: float = Field(default=0.15, ge=0.05, le=0.5)


class DriftDetectionResponse(BaseModel):
    """Response model for drift detection."""
    drift_detected: bool
    metrics: Dict
    recommendations: List[str]
    error: Optional[str] = None


# API Endpoints
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "module": "M5.3: Data Quality & Validation",
        "version": "1.0.0"
    }


@app.post("/quality/score", response_model=QualityScoreResponse)
def score_quality(request: QualityScoreRequest):
    """
    Score chunks for quality.

    Returns quality scores and pass/fail status for each chunk.
    """
    try:
        # Initialize scorer
        scorer = ChunkQualityScorer(
            min_score=request.min_score,
            optimal_length_min=request.optimal_length_min,
            optimal_length_max=request.optimal_length_max
        )

        # Prepare chunks for scoring
        chunks_to_score = []
        for chunk in request.chunks:
            metadata = None
            if chunk.metadata:
                metadata = ChunkMetadata(
                    source=chunk.metadata.source,
                    date=chunk.metadata.date,
                    section=chunk.metadata.section,
                    chunk_id=chunk.metadata.chunk_id
                )
            chunks_to_score.append((chunk.text, metadata))

        # Score chunks
        scores = scorer.batch_score(chunks_to_score)

        # Track metrics if enabled
        if config.ENABLE_PROMETHEUS:
            for score in scores:
                status = "passed" if score.passed else "failed_quality"
                chunks_processed.labels(status=status).inc()
                quality_score_hist.observe(score.total_score)

        # Build response
        passed_count = sum(1 for s in scores if s.passed)
        failed_count = len(scores) - passed_count
        pass_rate = (passed_count / len(scores) * 100) if scores else 0

        score_dicts = [
            {
                "chunk_id": request.chunks[i].chunk_id,
                "total_score": s.total_score,
                "passed": s.passed,
                "failure_reasons": s.failure_reasons,
                "breakdown": {
                    "information_density": s.information_density,
                    "semantic_completeness": s.semantic_completeness,
                    "readability": s.readability,
                    "metadata_quality": s.metadata_quality,
                    "length_appropriateness": s.length_appropriateness
                }
            }
            for i, s in enumerate(scores)
        ]

        logger.info(
            f"Quality scoring complete: {passed_count}/{len(scores)} passed "
            f"({pass_rate:.1f}%)"
        )

        return QualityScoreResponse(
            total_chunks=len(scores),
            passed_chunks=passed_count,
            failed_chunks=failed_count,
            pass_rate=round(pass_rate, 2),
            scores=score_dicts
        )

    except Exception as e:
        logger.error(f"Error scoring quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/duplicates/detect", response_model=DuplicateDetectionResponse)
def detect_duplicates(request: DuplicateDetectionRequest):
    """
    Detect duplicate chunks.

    Returns unique chunk IDs and information about detected duplicates.
    """
    try:
        # Initialize detector
        detector = DuplicateDetector(threshold=request.threshold)

        # Prepare chunks
        chunks = [(chunk.chunk_id, chunk.text) for chunk in request.chunks]

        # Detect duplicates
        unique_ids, dup_info = detector.deduplicate_batch(chunks)

        # Track metrics if enabled
        if config.ENABLE_PROMETHEUS:
            chunks_processed.labels(status="unique").inc(len(unique_ids))
            chunks_processed.labels(status="duplicate").inc(len(dup_info))

        # Build response
        dedup_rate = (len(dup_info) / len(chunks) * 100) if chunks else 0

        duplicate_dicts = [
            {
                "duplicate_chunk_id": dup_id,
                "original_chunk_id": orig_id,
                "similarity": round(sim, 4)
            }
            for dup_id, orig_id, sim in dup_info
        ]

        logger.info(
            f"Duplicate detection complete: {len(unique_ids)} unique, "
            f"{len(dup_info)} duplicates ({dedup_rate:.1f}%)"
        )

        return DuplicateDetectionResponse(
            total_chunks=len(chunks),
            unique_chunks=len(unique_ids),
            duplicates_found=len(dup_info),
            dedup_rate=round(dedup_rate, 2),
            unique_chunk_ids=unique_ids,
            duplicate_info=duplicate_dicts
        )

    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/drift/detect", response_model=DriftDetectionResponse)
def detect_drift(request: DriftDetectionRequest):
    """
    Detect data drift in quality metrics.

    Compares current batch against baseline to identify distribution shifts.
    Requires baseline to be set first (not implemented in this minimal API).
    """
    try:
        # Check if we have baseline data (in production, load from storage)
        # For this API, we'll return a graceful skip message
        clients = config.get_clients()

        if not clients.get("grafana"):
            return DriftDetectionResponse(
                drift_detected=False,
                metrics={},
                recommendations=[],
                error="No baseline data available. Set baseline first or configure Grafana."
            )

        # Initialize detector
        detector = DataDriftDetector(
            significance_level=request.significance_level,
            drift_threshold=request.drift_threshold
        )

        # In production, load baseline from storage/database
        # For demo, we'll skip gracefully
        logger.info("Drift detection requested but baseline not configured")

        return DriftDetectionResponse(
            drift_detected=False,
            metrics={},
            recommendations=[],
            error="Baseline not configured. This endpoint requires historical data."
        )

    except Exception as e:
        logger.error(f"Error detecting drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/validate")
def validate_pipeline(
    chunks: List[ChunkInput],
    min_quality_score: float = 70.0,
    similarity_threshold: float = 0.85
):
    """
    Complete validation pipeline: quality filtering + deduplication.

    This is the main endpoint that combines quality scoring and duplicate detection.
    """
    try:
        logger.info(f"Starting validation pipeline for {len(chunks)} chunks")

        # Step 1: Quality filtering
        chunks_for_quality = [
            (
                chunk.chunk_id,
                chunk.text,
                ChunkMetadata(
                    source=chunk.metadata.source if chunk.metadata else None,
                    date=chunk.metadata.date if chunk.metadata else None,
                    section=chunk.metadata.section if chunk.metadata else None,
                    chunk_id=chunk.metadata.chunk_id if chunk.metadata else None
                ) if chunk.metadata else None
            )
            for chunk in chunks
        ]

        passed_chunks, quality_scores = filter_low_quality_chunks(
            chunks_for_quality,
            min_score=min_quality_score
        )

        # Step 2: Deduplication
        unique_ids = remove_duplicates(passed_chunks, threshold=similarity_threshold)

        # Calculate metrics
        quality_pass_rate = (len(passed_chunks) / len(chunks) * 100) if chunks else 0
        dedup_rate = ((len(passed_chunks) - len(unique_ids)) / len(passed_chunks) * 100) if passed_chunks else 0
        final_pass_rate = (len(unique_ids) / len(chunks) * 100) if chunks else 0

        logger.info(
            f"Pipeline complete: {len(chunks)} → "
            f"{len(passed_chunks)} after quality → "
            f"{len(unique_ids)} after dedup"
        )

        return {
            "total_input_chunks": len(chunks),
            "after_quality_filter": len(passed_chunks),
            "after_deduplication": len(unique_ids),
            "final_chunks": len(unique_ids),
            "quality_pass_rate": round(quality_pass_rate, 2),
            "dedup_rate": round(dedup_rate, 2),
            "final_pass_rate": round(final_pass_rate, 2),
            "unique_chunk_ids": unique_ids
        }

    except Exception as e:
        logger.error(f"Error in validation pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Local development runner
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting M5.3 Data Quality API...")
    logger.info("Docs available at http://localhost:8000/docs")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
