"""
Configuration module for M5.3 Data Quality & Validation.

Handles environment variables and provides constants for quality validation.
"""

import os
from typing import Dict, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Quality Scoring Defaults
DEFAULT_MIN_QUALITY_SCORE = float(os.getenv("MIN_QUALITY_SCORE", "70.0"))
DEFAULT_OPTIMAL_LENGTH_MIN = int(os.getenv("OPTIMAL_LENGTH_MIN", "200"))
DEFAULT_OPTIMAL_LENGTH_MAX = int(os.getenv("OPTIMAL_LENGTH_MAX", "800"))

# Duplicate Detection Defaults
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
DEFAULT_NUM_PERMUTATIONS = int(os.getenv("NUM_PERMUTATIONS", "128"))

# Data Drift Defaults
DEFAULT_SIGNIFICANCE_LEVEL = float(os.getenv("SIGNIFICANCE_LEVEL", "0.05"))
DEFAULT_DRIFT_THRESHOLD = float(os.getenv("DRIFT_THRESHOLD", "0.15"))
MIN_DRIFT_SAMPLES = int(os.getenv("MIN_DRIFT_SAMPLES", "50"))

# Alert Thresholds (from production section)
ALERT_MIN_PASS_RATE = float(os.getenv("ALERT_MIN_PASS_RATE", "60.0"))  # %
ALERT_MAX_DRIFT_SCORE = float(os.getenv("ALERT_MAX_DRIFT_SCORE", "0.25"))
ALERT_MAX_DEDUP_RATE = float(os.getenv("ALERT_MAX_DEDUP_RATE", "25.0"))  # %
ALERT_MAX_PIPELINE_MINUTES = int(os.getenv("ALERT_MAX_PIPELINE_MINUTES", "45"))

# Monitoring Settings
ENABLE_PROMETHEUS = os.getenv("ENABLE_PROMETHEUS", "false").lower() == "true"
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8000"))
METRICS_BATCH_INTERVAL_SECONDS = int(os.getenv("METRICS_BATCH_INTERVAL_SECONDS", "60"))

# Processing Settings
ENABLE_MULTIPROCESSING = os.getenv("ENABLE_MULTIPROCESSING", "false").lower() == "true"
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "8"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))

# External Service Credentials (optional)
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY")
GRAFANA_URL = os.getenv("GRAFANA_URL")

AIRFLOW_API_KEY = os.getenv("AIRFLOW_API_KEY")
AIRFLOW_URL = os.getenv("AIRFLOW_URL")


def get_quality_config() -> Dict[str, any]:
    """
    Get quality scoring configuration.

    Returns:
        Dict with quality scoring parameters
    """
    return {
        "min_score": DEFAULT_MIN_QUALITY_SCORE,
        "optimal_length_min": DEFAULT_OPTIMAL_LENGTH_MIN,
        "optimal_length_max": DEFAULT_OPTIMAL_LENGTH_MAX,
    }


def get_duplicate_config() -> Dict[str, any]:
    """
    Get duplicate detection configuration.

    Returns:
        Dict with duplicate detection parameters
    """
    return {
        "threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "num_perm": DEFAULT_NUM_PERMUTATIONS,
    }


def get_drift_config() -> Dict[str, any]:
    """
    Get drift detection configuration.

    Returns:
        Dict with drift detection parameters
    """
    return {
        "significance_level": DEFAULT_SIGNIFICANCE_LEVEL,
        "drift_threshold": DEFAULT_DRIFT_THRESHOLD,
    }


def get_alert_thresholds() -> Dict[str, any]:
    """
    Get alert threshold configuration.

    Returns:
        Dict with alert thresholds for monitoring
    """
    return {
        "min_pass_rate": ALERT_MIN_PASS_RATE,
        "max_drift_score": ALERT_MAX_DRIFT_SCORE,
        "max_dedup_rate": ALERT_MAX_DEDUP_RATE,
        "max_pipeline_minutes": ALERT_MAX_PIPELINE_MINUTES,
    }


def get_clients() -> Dict[str, Optional[any]]:
    """
    Get external service clients if credentials are available.

    Returns:
        Dict with initialized clients or None if credentials missing
    """
    clients = {
        "grafana": None,
        "airflow": None,
    }

    # Grafana client (basic example - would use actual SDK)
    if GRAFANA_API_KEY and GRAFANA_URL:
        clients["grafana"] = {
            "api_key": GRAFANA_API_KEY,
            "url": GRAFANA_URL,
        }

    # Airflow client
    if AIRFLOW_API_KEY and AIRFLOW_URL:
        clients["airflow"] = {
            "api_key": AIRFLOW_API_KEY,
            "url": AIRFLOW_URL,
        }

    return clients


def validate_config() -> bool:
    """
    Validate configuration values are within acceptable ranges.

    Returns:
        True if config is valid, raises ValueError otherwise
    """
    if not (0 <= DEFAULT_MIN_QUALITY_SCORE <= 100):
        raise ValueError("MIN_QUALITY_SCORE must be between 0 and 100")

    if DEFAULT_OPTIMAL_LENGTH_MIN >= DEFAULT_OPTIMAL_LENGTH_MAX:
        raise ValueError("OPTIMAL_LENGTH_MIN must be less than OPTIMAL_LENGTH_MAX")

    if not (0 <= DEFAULT_SIMILARITY_THRESHOLD <= 1):
        raise ValueError("SIMILARITY_THRESHOLD must be between 0 and 1")

    if not (0 < DEFAULT_SIGNIFICANCE_LEVEL < 1):
        raise ValueError("SIGNIFICANCE_LEVEL must be between 0 and 1")

    if not (0 <= DEFAULT_DRIFT_THRESHOLD <= 1):
        raise ValueError("DRIFT_THRESHOLD must be between 0 and 1")

    return True


# Validate on import
validate_config()
