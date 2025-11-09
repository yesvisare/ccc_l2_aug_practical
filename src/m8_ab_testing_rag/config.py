"""
Configuration management for Module 8.2: A/B Testing for RAG Improvements

Loads configuration from environment variables and provides access to constants.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", None)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "rag_experiments")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# A/B Testing Constants
DEFAULT_TRAFFIC_SPLIT = float(os.getenv("DEFAULT_TRAFFIC_SPLIT", "0.5"))
MIN_SAMPLE_SIZE = int(os.getenv("MIN_SAMPLE_SIZE", "1000"))
SIGNIFICANCE_LEVEL = float(os.getenv("SIGNIFICANCE_LEVEL", "0.05"))
STATISTICAL_POWER = float(os.getenv("STATISTICAL_POWER", "0.8"))

# RAG Configuration (optional - for integration)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")

# Monitoring
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "false").lower() == "true"
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))

# Application Settings
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_database_connection():
    """
    Get database connection if configured.

    Returns:
        Database connection or None if not configured
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not configured, using in-memory storage")
        return None

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Database connection established")
        return conn
    except ImportError:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return None
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def get_openai_client():
    """
    Get OpenAI client if API key is configured.

    Returns:
        OpenAI client or None
    """
    if not OPENAI_API_KEY:
        logger.warning("⚠️ OPENAI_API_KEY not configured")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
        return client
    except ImportError:
        logger.error("openai package not installed. Install with: pip install openai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None


def get_anthropic_client():
    """
    Get Anthropic client if API key is configured.

    Returns:
        Anthropic client or None
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("⚠️ ANTHROPIC_API_KEY not configured")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Anthropic client initialized")
        return client
    except ImportError:
        logger.error("anthropic package not installed. Install with: pip install anthropic")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")
        return None


def validate_config() -> bool:
    """
    Validate that required configuration is present.

    Returns:
        True if config is valid, False otherwise
    """
    warnings = []

    if not DATABASE_URL:
        warnings.append("DATABASE_URL not set (using in-memory storage)")

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        warnings.append("No LLM API keys configured (demo mode only)")

    if warnings:
        logger.warning("Configuration warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")

    return True  # Always return True for demo mode


if __name__ == "__main__":
    # Configuration check
    logging.basicConfig(level=LOG_LEVEL)

    print("=" * 60)
    print("Configuration Status")
    print("=" * 60)
    print(f"Database: {'✅ Configured' if DATABASE_URL else '⚠️  Not configured (in-memory mode)'}")
    print(f"OpenAI: {'✅ Configured' if OPENAI_API_KEY else '⚠️  Not configured'}")
    print(f"Anthropic: {'✅ Configured' if ANTHROPIC_API_KEY else '⚠️  Not configured'}")
    print(f"Metrics: {'✅ Enabled' if ENABLE_METRICS else '❌ Disabled'}")
    print()
    print(f"A/B Testing Settings:")
    print(f"  Traffic split: {DEFAULT_TRAFFIC_SPLIT}")
    print(f"  Min sample size: {MIN_SAMPLE_SIZE}")
    print(f"  Significance level: {SIGNIFICANCE_LEVEL}")
    print(f"  Statistical power: {STATISTICAL_POWER}")
    print("=" * 60)

    validate_config()
