"""
Configuration management for Module 7.3: Custom Business Metrics
================================================================

Loads environment variables and provides configuration for:
- Prometheus metrics export
- Redis caching for cohort lookups
- ClickHouse (optional) for advanced analytics
- System defaults and thresholds
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================

@dataclass
class PrometheusConfig:
    """Prometheus metrics configuration."""
    enabled: bool = True
    port: int = 8000
    path: str = "/metrics"
    push_gateway_url: Optional[str] = None


@dataclass
class RedisConfig:
    """Redis cache configuration for fast cohort lookups."""
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 3600  # Cache TTL for cohort data


@dataclass
class ClickHouseConfig:
    """ClickHouse configuration for advanced analytics (optional)."""
    enabled: bool = False
    host: str = "localhost"
    port: int = 8123
    database: str = "rag_metrics"
    user: str = "default"
    password: Optional[str] = None


@dataclass
class MetricsConfig:
    """Business metrics configuration and thresholds."""
    # Performance thresholds
    cohort_lookup_max_ms: float = 10.0

    # Cardinality limits
    max_label_cardinality: int = 100

    # Satisfaction scale
    satisfaction_min: int = 1
    satisfaction_max: int = 5

    # Confidence thresholds
    low_confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.8

    # Hallucination rate alert threshold (percentage)
    hallucination_alert_threshold: float = 5.0

    # Activity thresholds for cohorts
    power_user_query_threshold: int = 100  # queries/month
    new_user_days: int = 30
    at_risk_days: int = 14

    # Cost tracking
    avg_query_cost_dollars: float = 0.005  # $0.005 per query


@dataclass
class AppConfig:
    """Overall application configuration."""
    prometheus: PrometheusConfig
    redis: RedisConfig
    clickhouse: ClickHouseConfig
    metrics: MetricsConfig

    # General settings
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Returns:
        AppConfig object with all configuration settings
    """
    # Prometheus configuration
    prometheus = PrometheusConfig(
        enabled=os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
        port=int(os.getenv("PROMETHEUS_PORT", "8000")),
        path=os.getenv("PROMETHEUS_PATH", "/metrics"),
        push_gateway_url=os.getenv("PROMETHEUS_PUSH_GATEWAY_URL")
    )

    # Redis configuration
    redis = RedisConfig(
        enabled=os.getenv("REDIS_ENABLED", "false").lower() == "true",
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "3600"))
    )

    # ClickHouse configuration
    clickhouse = ClickHouseConfig(
        enabled=os.getenv("CLICKHOUSE_ENABLED", "false").lower() == "true",
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "rag_metrics"),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD")
    )

    # Metrics configuration
    metrics = MetricsConfig(
        cohort_lookup_max_ms=float(os.getenv("COHORT_LOOKUP_MAX_MS", "10.0")),
        max_label_cardinality=int(os.getenv("MAX_LABEL_CARDINALITY", "100")),
        hallucination_alert_threshold=float(os.getenv("HALLUCINATION_ALERT_THRESHOLD", "5.0")),
        power_user_query_threshold=int(os.getenv("POWER_USER_QUERY_THRESHOLD", "100")),
        avg_query_cost_dollars=float(os.getenv("AVG_QUERY_COST_DOLLARS", "0.005"))
    )

    # Overall app configuration
    return AppConfig(
        prometheus=prometheus,
        redis=redis,
        clickhouse=clickhouse,
        metrics=metrics,
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO")
    )


def get_redis_client():
    """
    Get Redis client for cohort caching.

    Returns:
        Redis client if enabled, None otherwise
    """
    config = load_config()

    if not config.redis.enabled:
        return None

    try:
        import redis

        client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True
        )

        # Test connection
        client.ping()
        return client

    except ImportError:
        print("⚠️ Redis library not installed. Install with: pip install redis")
        return None
    except Exception as e:
        print(f"⚠️ Failed to connect to Redis: {e}")
        return None


def get_clickhouse_client():
    """
    Get ClickHouse client for advanced analytics.

    Returns:
        ClickHouse client if enabled, None otherwise
    """
    config = load_config()

    if not config.clickhouse.enabled:
        return None

    try:
        from clickhouse_driver import Client

        client = Client(
            host=config.clickhouse.host,
            port=config.clickhouse.port,
            database=config.clickhouse.database,
            user=config.clickhouse.user,
            password=config.clickhouse.password
        )

        # Test connection
        client.execute("SELECT 1")
        return client

    except ImportError:
        print("⚠️ ClickHouse library not installed. Install with: pip install clickhouse-driver")
        return None
    except Exception as e:
        print(f"⚠️ Failed to connect to ClickHouse: {e}")
        return None


def get_clients():
    """
    Get all configured external service clients.

    Returns:
        Dict with 'redis' and 'clickhouse' clients (may be None)
    """
    return {
        'redis': get_redis_client(),
        'clickhouse': get_clickhouse_client()
    }


# =============================================================================
# DEFAULTS AND CONSTANTS
# =============================================================================

# Default cost assumptions (USD)
DEFAULT_COSTS = {
    'prometheus_monthly': 20.0,      # Self-hosted on small instance
    'grafana_monthly': 0.0,          # Open source
    'clickhouse_monthly': 50.0,      # Optional, for >100K queries/month
    'redis_monthly': 15.0,           # For cohort caching
}

# Query volume thresholds
VOLUME_THRESHOLDS = {
    'small': 1000,        # <1K queries/month
    'medium': 10000,      # 1K-10K queries/month
    'large': 100000,      # 10K-100K queries/month
    'enterprise': 1000000 # >100K queries/month
}

# Prometheus retention policies
RETENTION_POLICIES = {
    'raw_metrics': '15d',           # Raw data for 15 days
    'aggregated_hourly': '60d',     # Hourly aggregates for 60 days
    'aggregated_daily': '365d',     # Daily aggregates for 1 year
}


# =============================================================================
# CLI USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Configuration Status")
    print("=" * 70)

    config = load_config()

    print(f"\nEnvironment: {config.environment}")
    print(f"Debug mode: {config.debug}")
    print(f"Log level: {config.log_level}")

    print("\n[Prometheus]")
    print(f"  Enabled: {config.prometheus.enabled}")
    print(f"  Port: {config.prometheus.port}")
    print(f"  Path: {config.prometheus.path}")

    print("\n[Redis]")
    print(f"  Enabled: {config.redis.enabled}")
    if config.redis.enabled:
        print(f"  Host: {config.redis.host}:{config.redis.port}")
        print(f"  DB: {config.redis.db}")

    print("\n[ClickHouse]")
    print(f"  Enabled: {config.clickhouse.enabled}")
    if config.clickhouse.enabled:
        print(f"  Host: {config.clickhouse.host}:{config.clickhouse.port}")
        print(f"  Database: {config.clickhouse.database}")

    print("\n[Metrics Config]")
    print(f"  Cohort lookup max: {config.metrics.cohort_lookup_max_ms}ms")
    print(f"  Max label cardinality: {config.metrics.max_label_cardinality}")
    print(f"  Hallucination alert threshold: {config.metrics.hallucination_alert_threshold}%")
    print(f"  Avg query cost: ${config.metrics.avg_query_cost_dollars}")

    print("\n[Testing connections...]")
    clients = get_clients()
    print(f"  Redis: {'✓ Connected' if clients['redis'] else '✗ Not available'}")
    print(f"  ClickHouse: {'✓ Connected' if clients['clickhouse'] else '✗ Not available'}")

    print("\n" + "=" * 70)
