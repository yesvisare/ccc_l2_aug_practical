"""
Configuration management for Module 8.3: Regression Testing & CI/CD.

Loads environment variables and provides client factories for external services.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Test Configuration (from script)
DEFAULT_TEST_SUBSET_SIZE = 50  # Script: 50-question subset for fast CI
FULL_TEST_SIZE = 500  # Script: full evaluation size
CANARY_TEST_SIZE = 10  # Script: canary deployment test size

# Threshold Constants (from script)
FAITHFULNESS_THRESHOLD = 0.75
ANSWER_RELEVANCY_THRESHOLD = 0.70
CONTEXT_PRECISION_THRESHOLD = 0.65
P95_LATENCY_THRESHOLD_MS = 2000
COST_PER_QUERY_THRESHOLD = 0.01

# Flaky Test Handling (from script - Common Failure #2)
FLAKY_TEST_RUNS = 5  # Run tests 5 times
FLAKY_TOLERANCE_PCT = 20.0  # ±20% tolerance band

# Threshold Calibration (from script - Common Failure #3)
THRESHOLD_NUM_STD = 2.0  # baseline - 2*std
TARGET_FALSE_POSITIVE_RATE = 0.05  # 2-5% target

# DVC Configuration (from script - Step 3)
DVC_REMOTE_NAME = "s3storage"
DVC_MODELS_DIR = Path("models")
DVC_MIN_VERSIONS = 10  # Script: retain minimum 10 versions
DVC_RETENTION_DAYS = 90  # Script: 90-day retention

# Safe Deployment (from script - Step 4)
CANARY_PASS_THRESHOLD = 0.80  # 80% pass rate for canary

# CI/CD Timing (from script)
CI_TIMEOUT_MINUTES = 10  # Script: CI should be <10 minutes
FAST_TEST_TARGET_MINUTES = 5  # Script: aim for <5 minutes

# Baseline file path
BASELINE_METRICS_FILE = Path("baseline_metrics.json")

# Test data paths
TEST_DATA_DIR = Path("test_data")
EXAMPLE_DATA_FILE = TEST_DATA_DIR / "example_data.json"


# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

def get_env(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Get environment variable with optional default and required validation.

    Args:
        key: Environment variable key
        default: Default value if not found
        required: If True, raise error when missing

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required=True and variable not found
    """
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"Required environment variable {key} not set")
    return value


# OpenAI Configuration
OPENAI_API_KEY = get_env("OPENAI_API_KEY")
OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_EMBEDDING_MODEL = get_env("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

# DVC/S3 Configuration
AWS_ACCESS_KEY_ID = get_env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get_env("AWS_SECRET_ACCESS_KEY")
AWS_REGION = get_env("AWS_REGION", "us-east-1")
S3_BUCKET = get_env("S3_BUCKET")

# GitHub Configuration (for CI/CD)
GITHUB_TOKEN = get_env("GITHUB_TOKEN")
GITHUB_REPOSITORY = get_env("GITHUB_REPOSITORY")

# Monitoring/Logging
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")


# ============================================================================
# CLIENT FACTORIES
# ============================================================================

def get_openai_client() -> Optional[Any]:
    """
    Get OpenAI client if API key is available.

    Returns:
        OpenAI client instance or None if key not available
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not set - client unavailable")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
        return client
    except ImportError:
        logger.error("openai package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None


def get_s3_client() -> Optional[Any]:
    """
    Get boto3 S3 client if AWS credentials are available.

    Returns:
        boto3 S3 client or None if credentials not available
    """
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.warning("AWS credentials not set - S3 client unavailable")
        return None

    try:
        import boto3
        client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logger.info("S3 client initialized")
        return client
    except ImportError:
        logger.error("boto3 package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


def get_clients() -> Dict[str, Any]:
    """
    Get all available clients.

    Returns:
        Dict mapping client names to client instances (or None if unavailable)
    """
    clients = {
        'openai': get_openai_client(),
        's3': get_s3_client()
    }

    available = [name for name, client in clients.items() if client is not None]
    logger.info(f"Available clients: {', '.join(available) if available else 'none'}")

    return clients


def has_required_services() -> bool:
    """
    Check if all required services are configured.

    Returns:
        True if OpenAI is available (minimum requirement)
    """
    return OPENAI_API_KEY is not None


# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================

def validate_config() -> Dict[str, bool]:
    """
    Validate configuration and return status.

    Returns:
        Dict with validation results for each component
    """
    validation = {
        'openai': OPENAI_API_KEY is not None,
        'aws_s3': AWS_ACCESS_KEY_ID is not None and AWS_SECRET_ACCESS_KEY is not None,
        'github': GITHUB_TOKEN is not None,
        'test_data': EXAMPLE_DATA_FILE.exists(),
        'baseline_metrics': BASELINE_METRICS_FILE.exists()
    }

    logger.info("Configuration validation:")
    for component, status in validation.items():
        status_str = "✓" if status else "✗"
        logger.info(f"  {status_str} {component}")

    return validation


# ============================================================================
# CONFIGURATION INFO
# ============================================================================

def get_config_info() -> Dict[str, Any]:
    """
    Get current configuration information.

    Returns:
        Dict with configuration details
    """
    return {
        'test_config': {
            'subset_size': DEFAULT_TEST_SUBSET_SIZE,
            'full_size': FULL_TEST_SIZE,
            'canary_size': CANARY_TEST_SIZE
        },
        'thresholds': {
            'faithfulness': FAITHFULNESS_THRESHOLD,
            'answer_relevancy': ANSWER_RELEVANCY_THRESHOLD,
            'context_precision': CONTEXT_PRECISION_THRESHOLD,
            'p95_latency_ms': P95_LATENCY_THRESHOLD_MS,
            'cost_per_query': COST_PER_QUERY_THRESHOLD
        },
        'flaky_test_handling': {
            'num_runs': FLAKY_TEST_RUNS,
            'tolerance_pct': FLAKY_TOLERANCE_PCT
        },
        'dvc': {
            'models_dir': str(DVC_MODELS_DIR),
            'min_versions': DVC_MIN_VERSIONS,
            'retention_days': DVC_RETENTION_DAYS
        },
        'ci_cd': {
            'timeout_minutes': CI_TIMEOUT_MINUTES,
            'fast_test_target_minutes': FAST_TEST_TARGET_MINUTES,
            'canary_pass_threshold': CANARY_PASS_THRESHOLD
        },
        'models': {
            'openai_model': OPENAI_MODEL,
            'embedding_model': OPENAI_EMBEDDING_MODEL
        },
        'services_available': validate_config()
    }


if __name__ == "__main__":
    """Test configuration loading."""
    import json

    print("=" * 70)
    print("Configuration Test")
    print("=" * 70)
    print()

    # Validate configuration
    print("Validating configuration...")
    validation = validate_config()
    print()

    # Get config info
    print("Configuration details:")
    config_info = get_config_info()
    print(json.dumps(config_info, indent=2))
    print()

    # Test client initialization
    print("Testing client initialization...")
    clients = get_clients()
    print()

    print("=" * 70)
    print("Configuration test completed")
    print("=" * 70)
