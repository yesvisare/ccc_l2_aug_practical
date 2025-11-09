"""
FastAPI router for Module 7.4: Intelligent Alerting.

Provides REST API endpoints for anomaly detection, alert aggregation,
and incident management without business logic in the API layer.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from src.m7_intelligent_alerting_workspace.config import Config, get_clients
from src.m7_intelligent_alerting_workspace.core import (
    AnomalyDetector,
    AlertAggregator,
    PagerDutyIntegration,
    RunbookAutomation,
    Alert,
    load_example_data
)

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Global state (in production, use proper state management)
_detector: Optional[AnomalyDetector] = None
_aggregator: AlertAggregator = AlertAggregator()
_pagerduty: Optional[PagerDutyIntegration] = None
_automation: RunbookAutomation = RunbookAutomation()


# Request/Response Models
class HealthResponse(BaseModel):
    status: str
    environment: str
    prometheus_configured: bool
    pagerduty_configured: bool


class TrainRequest(BaseModel):
    metric_name: str = Field(..., description="Prometheus metric name")
    baseline_days: int = Field(7, description="Days of historical data for training")
    std_threshold: float = Field(3.0, description="Standard deviation threshold")


class TrainResponse(BaseModel):
    success: bool
    message: str
    data_points: int = 0
    skipped: bool = False


class DetectRequest(BaseModel):
    timestamp: datetime
    value: float
    metric_name: Optional[str] = None


class DetectResponse(BaseModel):
    timestamp: datetime
    actual_value: float
    predicted_value: float
    is_anomaly: bool
    severity: Optional[str]
    sigma_deviation: float
    skipped: bool = False


class AlertRequest(BaseModel):
    id: str
    metric: str
    service: str
    timestamp: datetime
    severity: str
    message: str
    labels: Dict[str, str] = Field(default_factory=dict)


class AlertResponse(BaseModel):
    received: bool
    alert_id: str


class AggregateResponse(BaseModel):
    incident_count: int
    incidents: List[Dict[str, Any]]


class RunbookRequest(BaseModel):
    trigger: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RunbookResponse(BaseModel):
    executed: bool
    trigger: str
    result: Optional[str] = None
    reason: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        environment=Config.ENVIRONMENT,
        prometheus_configured=bool(Config.PROMETHEUS_URL),
        pagerduty_configured=Config.has_pagerduty()
    )


@router.post("/train", response_model=TrainResponse)
async def train_model(request: TrainRequest):
    """
    Train anomaly detection model on historical data.

    Requires Prometheus to be configured and accessible.
    """
    global _detector

    if not Config.PROMETHEUS_URL:
        logger.warning("⚠️ Skipping model training (no Prometheus configured)")
        return TrainResponse(
            success=False,
            message="Prometheus not configured",
            skipped=True
        )

    try:
        # In production: fetch real data from Prometheus
        # For demo: generate synthetic baseline
        logger.info(f"Training model with {request.baseline_days} days of data...")

        # Generate synthetic baseline (in production: use fetch_prometheus_metrics)
        data_points = request.baseline_days * 24 * 60  # 1-minute resolution
        baseline_df = pd.DataFrame({
            'ds': pd.date_range(
                start=datetime.now() - timedelta(days=request.baseline_days),
                periods=data_points,
                freq='1min'
            ),
            'y': np.random.normal(0.15, 0.02, data_points)
        })

        # Train detector
        _detector = AnomalyDetector(std_threshold=request.std_threshold)
        success = _detector.train(baseline_df)

        if success:
            return TrainResponse(
                success=True,
                message="Model trained successfully",
                data_points=len(baseline_df)
            )
        else:
            return TrainResponse(
                success=False,
                message="Training failed"
            )

    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training failed: {str(e)}"
        )


@router.post("/detect", response_model=DetectResponse)
async def detect_anomaly(request: DetectRequest):
    """
    Detect if a single data point is anomalous.

    Requires model to be trained first via /train endpoint.
    """
    if _detector is None or not _detector.trained:
        logger.warning("⚠️ Model not trained, cannot detect anomalies")
        return DetectResponse(
            timestamp=request.timestamp,
            actual_value=request.value,
            predicted_value=request.value,
            is_anomaly=False,
            severity=None,
            sigma_deviation=0.0,
            skipped=True
        )

    try:
        result = _detector.detect({
            'timestamp': request.timestamp,
            'value': request.value
        })

        return DetectResponse(
            timestamp=result.timestamp,
            actual_value=result.actual_value,
            predicted_value=result.predicted_value,
            is_anomaly=result.is_anomaly,
            severity=result.severity,
            sigma_deviation=result.sigma_deviation
        )

    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}"
        )


@router.post("/alerts/ingest", response_model=AlertResponse)
async def ingest_alert(alert: AlertRequest):
    """
    Ingest alert for aggregation.

    Alerts are buffered and aggregated via /alerts/aggregate endpoint.
    """
    try:
        alert_obj = Alert(
            id=alert.id,
            metric=alert.metric,
            service=alert.service,
            timestamp=alert.timestamp,
            severity=alert.severity,
            message=alert.message,
            labels=alert.labels
        )

        _aggregator.add_alert(alert_obj)
        logger.info(f"Alert ingested: {alert.id}")

        return AlertResponse(
            received=True,
            alert_id=alert.id
        )

    except Exception as e:
        logger.error(f"Alert ingestion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alert ingestion failed: {str(e)}"
        )


@router.post("/alerts/aggregate", response_model=AggregateResponse)
async def aggregate_alerts():
    """
    Aggregate buffered alerts into incidents.

    Groups alerts by service and time window.
    """
    try:
        incidents = _aggregator.aggregate()

        return AggregateResponse(
            incident_count=len(incidents),
            incidents=[
                {
                    "id": inc.id,
                    "service": inc.service,
                    "timestamp": inc.timestamp.isoformat(),
                    "severity": inc.severity,
                    "alert_count": inc.alert_count,
                    "summary": inc.summary
                }
                for inc in incidents
            ]
        )

    except Exception as e:
        logger.error(f"Aggregation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Aggregation failed: {str(e)}"
        )


@router.post("/runbook/execute", response_model=RunbookResponse)
async def execute_runbook(request: RunbookRequest):
    """
    Execute automated remediation runbook.

    Requires AUTO_REMEDIATION_ENABLED=true in configuration.
    """
    try:
        result = _automation.execute(request.trigger, request.parameters)

        return RunbookResponse(
            executed=result.get("executed", False),
            trigger=request.trigger,
            result=result.get("result"),
            reason=result.get("reason")
        )

    except Exception as e:
        logger.error(f"Runbook execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Runbook execution failed: {str(e)}"
        )


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint (optional).

    Returns basic metrics about the alerting system.
    """
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest()
    except ImportError:
        return {"error": "prometheus-client not available"}


# Startup handler
def initialize_services():
    """Initialize services on startup."""
    global _pagerduty

    logger.info(f"Starting Intelligent Alerting API (env={Config.ENVIRONMENT})")

    # Initialize PagerDuty if configured
    if Config.has_pagerduty():
        _pagerduty = PagerDutyIntegration()
        logger.info("PagerDuty integration enabled")
    else:
        logger.info("PagerDuty integration disabled (no credentials)")

    # Validate configuration
    Config.validate()
