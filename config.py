"""
Configuration management for Module 7.4: Intelligent Alerting.
Loads environment variables and provides client initialization.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for intelligent alerting system."""

    # Prometheus Configuration
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    PROMETHEUS_METRIC_NAME: str = os.getenv("PROMETHEUS_METRIC_NAME", "http_request_duration_seconds")

    # PagerDuty Configuration
    PAGERDUTY_API_KEY: Optional[str] = os.getenv("PAGERDUTY_API_KEY")
    PAGERDUTY_SERVICE_ID: Optional[str] = os.getenv("PAGERDUTY_SERVICE_ID")
    PAGERDUTY_INTEGRATION_KEY: Optional[str] = os.getenv("PAGERDUTY_INTEGRATION_KEY")

    # Anomaly Detection Settings
    ANOMALY_STD_THRESHOLD: float = float(os.getenv("ANOMALY_STD_THRESHOLD", "3.0"))
    ANOMALY_INTERVAL_WIDTH: float = float(os.getenv("ANOMALY_INTERVAL_WIDTH", "0.997"))
    ANOMALY_SEASONALITY_MODE: str = os.getenv("ANOMALY_SEASONALITY_MODE", "multiplicative")

    # Alert Aggregation Settings
    ALERT_AGGREGATION_WINDOW: int = int(os.getenv("ALERT_AGGREGATION_WINDOW", "300"))
    ALERT_AGGREGATION_ENABLED: bool = os.getenv("ALERT_AGGREGATION_ENABLED", "true").lower() == "true"

    # Auto-Remediation Settings
    AUTO_REMEDIATION_ENABLED: bool = os.getenv("AUTO_REMEDIATION_ENABLED", "false").lower() == "true"
    RUNBOOK_PATH: str = os.getenv("RUNBOOK_PATH", "./runbooks")

    # Application Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        required = []

        if not cls.PROMETHEUS_URL:
            required.append("PROMETHEUS_URL")

        if required:
            logger.warning(f"Missing required configuration: {', '.join(required)}")
            return False

        return True

    @classmethod
    def has_pagerduty(cls) -> bool:
        """Check if PagerDuty configuration is available."""
        return bool(cls.PAGERDUTY_API_KEY and cls.PAGERDUTY_SERVICE_ID)


def get_clients() -> Dict[str, Any]:
    """
    Initialize and return external service clients.

    Returns:
        Dictionary containing initialized clients (prometheus, pagerduty)
    """
    clients = {}

    # Prometheus client
    try:
        from prometheus_api_client import PrometheusConnect
        clients["prometheus"] = PrometheusConnect(url=Config.PROMETHEUS_URL, disable_ssl=True)
        logger.info(f"Prometheus client initialized: {Config.PROMETHEUS_URL}")
    except Exception as e:
        logger.warning(f"Failed to initialize Prometheus client: {e}")
        clients["prometheus"] = None

    # PagerDuty client
    if Config.has_pagerduty():
        try:
            from pdpyras import APISession
            clients["pagerduty"] = APISession(Config.PAGERDUTY_API_KEY)
            logger.info("PagerDuty client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize PagerDuty client: {e}")
            clients["pagerduty"] = None
    else:
        logger.info("PagerDuty configuration not available, skipping client initialization")
        clients["pagerduty"] = None

    return clients


# Constants
DEFAULT_BASELINE_DAYS = 7
DEFAULT_CHECK_WINDOW_SECONDS = 300
MAX_ALERTS_PER_INCIDENT = 10
ANOMALY_SEVERITY_LEVELS = {
    "low": (3.0, 4.0),      # 3-4 sigma
    "medium": (4.0, 5.0),   # 4-5 sigma
    "high": (5.0, float('inf'))  # >5 sigma
}
