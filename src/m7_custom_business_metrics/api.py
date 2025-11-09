"""
FastAPI Router for Module 7.3: Custom Business Metrics
======================================================

All API endpoints for recording business metrics and querying KPIs.
Extracted from app.py (no logic changes).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, validator
from starlette.responses import Response

# Import module functions
from .core import (
    QueryMetrics,
    UserCohort,
    QueryAccuracy,
    FeatureType,
    record_query_metrics,
    get_user_cohort,
    update_hallucination_rate,
    update_active_users,
    record_cost,
    update_feature_success_rate,
    generate_executive_summary
)
from .config import load_config, get_clients

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Check if external services are available
clients = get_clients()
REDIS_AVAILABLE = clients['redis'] is not None
CLICKHOUSE_AVAILABLE = clients['clickhouse'] is not None

# Create router
router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UserMetadataModel(BaseModel):
    """User metadata for cohort determination."""
    tier: str = "free"
    days_since_signup: int = 0
    query_count: int = 0
    days_since_last_query: int = 0


class QueryMetricsRequest(BaseModel):
    """Request model for recording query metrics."""
    query_id: str
    user_id: str
    user_metadata: Optional[UserMetadataModel] = None
    accuracy: str = Field(..., description="One of: accurate, partial, inaccurate, hallucinated")
    satisfaction: Optional[int] = Field(None, ge=1, le=5, description="1-5 scale")
    confidence: float = Field(..., ge=0.0, le=1.0)
    feature: str = Field(..., description="One of: simple_qa, summarization, multi_doc, conversational")
    latency_ms: float

    @validator('accuracy')
    def validate_accuracy(cls, v):
        try:
            QueryAccuracy(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid accuracy: {v}")

    @validator('feature')
    def validate_feature(cls, v):
        try:
            FeatureType(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid feature: {v}")


class HallucinationRateRequest(BaseModel):
    """Request model for updating hallucination rate."""
    cohort: str
    total_queries: int = Field(..., ge=0)
    hallucinated_queries: int = Field(..., ge=0)


class ActiveUsersRequest(BaseModel):
    """Request model for updating active users."""
    cohort: str
    count: int = Field(..., ge=0)


class CostRequest(BaseModel):
    """Request model for recording costs."""
    cohort: str
    cost_dollars: float = Field(..., ge=0.0)


class FeatureSuccessRequest(BaseModel):
    """Request model for updating feature success rates."""
    feature: str
    total_uses: int = Field(..., ge=0)
    successful_uses: int = Field(..., ge=0)


class KPIQueryRequest(BaseModel):
    """Request model for querying KPIs."""
    time_period: str = "last_7_days"
    cohorts: Optional[List[str]] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Module 7.3: Custom Business Metrics",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "record_query": "POST /api/metrics/query",
            "hallucination_rate": "POST /api/metrics/hallucination_rate",
            "active_users": "POST /api/metrics/active_users",
            "cost": "POST /api/metrics/cost",
            "feature_success": "POST /api/metrics/feature_success",
            "kpi_summary": "POST /api/kpi/summary",
            "prometheus_metrics": "GET /api/metrics"
        },
        "docs": "/docs",
        "services": {
            "redis": "available" if REDIS_AVAILABLE else "not configured",
            "clickhouse": "available" if CLICKHOUSE_AVAILABLE else "not configured"
        }
    }


@router.post("/metrics/query")
async def record_query(request: QueryMetricsRequest):
    """
    Record business metrics for a single query.

    Returns 200 even if external services are unavailable (graceful degradation).
    """
    try:
        # Determine cohort
        user_metadata = None
        if request.user_metadata:
            user_metadata = {
                'tier': request.user_metadata.tier,
                'days_since_signup': request.user_metadata.days_since_signup,
                'query_count': request.user_metadata.query_count,
                'days_since_last_query': request.user_metadata.days_since_last_query
            }

        cohort = get_user_cohort(request.user_id, user_metadata)

        # Create metrics object
        metrics = QueryMetrics(
            query_id=request.query_id,
            user_id=request.user_id,
            cohort=cohort,
            accuracy=QueryAccuracy(request.accuracy),
            satisfaction=request.satisfaction,
            confidence=request.confidence,
            feature=FeatureType(request.feature),
            timestamp=datetime.utcnow(),
            latency_ms=request.latency_ms
        )

        # Record metrics
        record_query_metrics(metrics)

        return {
            "status": "recorded",
            "query_id": request.query_id,
            "cohort": cohort.value,
            "timestamp": metrics.timestamp.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to record query metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/hallucination_rate")
async def update_hallucination(request: HallucinationRateRequest):
    """Update hallucination rate for a cohort."""
    try:
        cohort = UserCohort(request.cohort)
        rate = update_hallucination_rate(
            cohort=cohort,
            total_queries=request.total_queries,
            hallucinated_queries=request.hallucinated_queries
        )

        return {
            "status": "updated",
            "cohort": cohort.value,
            "hallucination_rate": round(rate, 2)
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update hallucination rate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/active_users")
async def update_users(request: ActiveUsersRequest):
    """Update active user count for a cohort."""
    try:
        cohort = UserCohort(request.cohort)
        update_active_users(cohort=cohort, count=request.count)

        return {
            "status": "updated",
            "cohort": cohort.value,
            "count": request.count
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update active users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/cost")
async def record_cohort_cost(request: CostRequest):
    """Record incremental cost for a cohort."""
    try:
        cohort = UserCohort(request.cohort)
        record_cost(cohort=cohort, cost_dollars=request.cost_dollars)

        return {
            "status": "recorded",
            "cohort": cohort.value,
            "cost_dollars": round(request.cost_dollars, 4)
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to record cost: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/feature_success")
async def update_feature_success(request: FeatureSuccessRequest):
    """Update feature success rate."""
    try:
        feature = FeatureType(request.feature)
        rate = update_feature_success_rate(
            feature=feature,
            total_uses=request.total_uses,
            successful_uses=request.successful_uses
        )

        return {
            "status": "updated",
            "feature": feature.value,
            "success_rate": round(rate, 2)
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update feature success rate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kpi/summary")
async def get_kpi_summary(request: KPIQueryRequest):
    """
    Generate executive KPI summary.

    Note: Returns mock data structure. In production, would query
    Prometheus/ClickHouse for actual metrics.
    """
    if not REDIS_AVAILABLE and not CLICKHOUSE_AVAILABLE:
        logger.warning("No storage backend available for KPI queries")

    try:
        summary = generate_executive_summary(time_period=request.time_period)

        # Filter by cohorts if specified
        if request.cohorts:
            filtered_cohorts = {
                k: v for k, v in summary['kpis']['cohort_metrics'].items()
                if k in request.cohorts
            }
            summary['kpis']['cohort_metrics'] = filtered_cohorts

        return summary

    except Exception as e:
        logger.error(f"Failed to generate KPI summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    try:
        metrics = generate_latest()
        return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
