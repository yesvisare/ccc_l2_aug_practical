"""
Configuration module for OpenTelemetry distributed tracing.

Reads environment variables from .env and provides configuration for:
- OpenTelemetry tracer setup
- Jaeger endpoint configuration
- Sampling rates per environment
- Service metadata
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class TracingConfig:
    """
    Configuration for OpenTelemetry distributed tracing.

    Environment-specific sampling rates:
    - Development: 100% (trace everything for debugging)
    - Staging: 50% (balance visibility and cost)
    - Production: 10% (reduce overhead and storage)
    """

    # Service identification
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "rag-compliance-copilot")
    SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "2.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # OpenTelemetry OTLP endpoint
    OTLP_ENDPOINT: str = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    OTLP_INSECURE: bool = os.getenv("OTLP_INSECURE", "true").lower() == "true"

    # Sampling configuration
    SAMPLING_RATE: float = float(os.getenv("SAMPLING_RATE", "1.0"))

    # BatchSpanProcessor configuration
    # Trade-offs:
    # - Higher max_queue_size: More buffering, less blocking, more memory (5KB/span)
    # - Higher max_export_batch_size: Fewer network calls, more latency variance
    # - Lower schedule_delay_millis: Faster trace visibility, more network overhead
    MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "2048"))
    MAX_EXPORT_BATCH_SIZE: int = int(os.getenv("MAX_EXPORT_BATCH_SIZE", "512"))
    SCHEDULE_DELAY_MILLIS: int = int(os.getenv("SCHEDULE_DELAY_MILLIS", "5000"))

    # Jaeger UI URL (for documentation/links)
    JAEGER_UI_URL: str = os.getenv("JAEGER_UI_URL", "http://localhost:16686")

    # Enable/disable tracing (graceful degradation if Jaeger unavailable)
    TRACING_ENABLED: bool = os.getenv("TRACING_ENABLED", "true").lower() == "true"

    @classmethod
    def get_sampling_rate_for_env(cls, environment: str) -> float:
        """
        Get recommended sampling rate for environment.

        Args:
            environment: Environment name (development, staging, production)

        Returns:
            Sampling rate (0.0 to 1.0)

        Recommendations from script:
        - Development: 1.0 (100%) - Trace everything
        - Staging: 0.5 (50%) - Balance visibility and cost
        - Production: 0.1 (10%) - Reduce overhead from 15ms to 1.5ms
        """
        rates = {
            "development": 1.0,
            "staging": 0.5,
            "production": 0.1
        }
        return rates.get(environment.lower(), 0.1)

    @classmethod
    def to_dict(cls) -> Dict[str, any]:
        """Export configuration as dictionary."""
        return {
            "service_name": cls.SERVICE_NAME,
            "service_version": cls.SERVICE_VERSION,
            "environment": cls.ENVIRONMENT,
            "otlp_endpoint": cls.OTLP_ENDPOINT,
            "sampling_rate": cls.SAMPLING_RATE,
            "max_queue_size": cls.MAX_QUEUE_SIZE,
            "max_export_batch_size": cls.MAX_EXPORT_BATCH_SIZE,
            "schedule_delay_millis": cls.SCHEDULE_DELAY_MILLIS,
            "jaeger_ui_url": cls.JAEGER_UI_URL,
            "tracing_enabled": cls.TRACING_ENABLED
        }


class AppConfig:
    """
    Application configuration for FastAPI service.
    """

    # FastAPI settings
    APP_NAME: str = os.getenv("APP_NAME", "RAG Tracing Demo")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS settings (if needed)
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")

    # Request defaults
    DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "10"))
    DEFAULT_TOP_N: int = int(os.getenv("DEFAULT_TOP_N", "5"))
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-4")


def get_tracing_config() -> TracingConfig:
    """
    Get tracing configuration with environment-specific defaults.

    Returns:
        TracingConfig instance

    Note:
        If SAMPLING_RATE is not set, uses environment-based default.
    """
    config = TracingConfig()

    # Override sampling rate with environment default if not explicitly set
    if "SAMPLING_RATE" not in os.environ:
        config.SAMPLING_RATE = config.get_sampling_rate_for_env(config.ENVIRONMENT)

    return config


def get_app_config() -> AppConfig:
    """
    Get application configuration.

    Returns:
        AppConfig instance
    """
    return AppConfig()


def validate_config() -> Dict[str, bool]:
    """
    Validate configuration and check if Jaeger is reachable.

    Returns:
        Dictionary with validation results

    Checks:
    - Tracing enabled
    - OTLP endpoint reachable
    - Sampling rate in valid range
    """
    results = {
        "tracing_enabled": TracingConfig.TRACING_ENABLED,
        "valid_sampling_rate": 0.0 <= TracingConfig.SAMPLING_RATE <= 1.0,
        "otlp_endpoint_configured": bool(TracingConfig.OTLP_ENDPOINT),
    }

    # Try to check if Jaeger is reachable (optional, non-blocking)
    try:
        import socket
        # Parse endpoint
        if "://" in TracingConfig.OTLP_ENDPOINT:
            endpoint = TracingConfig.OTLP_ENDPOINT.split("://")[1]
        else:
            endpoint = TracingConfig.OTLP_ENDPOINT

        host, port = endpoint.split(":")
        port = int(port)

        # Quick socket check
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()

        results["jaeger_reachable"] = (result == 0)
    except Exception:
        results["jaeger_reachable"] = False

    return results


# Export configuration instances for easy import
tracing_config = get_tracing_config()
app_config = get_app_config()


if __name__ == "__main__":
    print("Tracing Configuration")
    print("=" * 60)

    config = get_tracing_config()
    for key, value in config.to_dict().items():
        print(f"{key:30s}: {value}")

    print("\nValidation Results")
    print("=" * 60)
    validation = validate_config()
    for key, value in validation.items():
        status = "✅" if value else "❌"
        print(f"{status} {key:30s}: {value}")

    if not validation["jaeger_reachable"]:
        print("\n⚠️  Jaeger not reachable. Start with:")
        print("   docker run -d --name jaeger \\")
        print("     -e COLLECTOR_OTLP_ENABLED=true \\")
        print("     -p 16686:16686 -p 4317:4317 -p 4318:4318 \\")
        print("     jaegertracing/all-in-one:1.51")
