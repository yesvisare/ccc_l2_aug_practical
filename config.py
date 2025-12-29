"""
Module 7.2: Application Performance Monitoring - Configuration
Manages Datadog APM configuration with production-safe defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class APMConfig:
    """APM configuration for Datadog with production-safe defaults."""

    # Datadog credentials
    DD_API_KEY: str = os.getenv("DD_API_KEY", "")
    DD_SITE: str = os.getenv("DD_SITE", "datadoghq.com")  # or datadoghq.eu
    DD_SERVICE: str = os.getenv("DD_SERVICE", "compliance-copilot-rag")
    DD_ENV: str = os.getenv("DD_ENV", "production")
    DD_VERSION: str = os.getenv("DD_VERSION", "1.0.0")

    # APM Configuration (Production-Safe)
    DD_PROFILING_ENABLED: bool = os.getenv("DD_PROFILING_ENABLED", "true").lower() == "true"
    DD_PROFILING_CAPTURE_PCT: int = int(os.getenv("DD_PROFILING_CAPTURE_PCT", "1"))  # 1% profiling
    DD_TRACE_SAMPLE_RATE: float = float(os.getenv("DD_TRACE_SAMPLE_RATE", "0.1"))  # 10% sampling
    DD_TRACE_ANALYTICS_ENABLED: bool = os.getenv("DD_TRACE_ANALYTICS_ENABLED", "true").lower() == "true"

    # Performance overhead limits
    DD_PROFILING_MAX_TIME_USAGE_PCT: float = float(os.getenv("DD_PROFILING_MAX_TIME_USAGE_PCT", "5"))  # Max 5% CPU
    DD_PROFILING_MEMORY_ENABLED: bool = os.getenv("DD_PROFILING_MEMORY_ENABLED", "true").lower() == "true"
    DD_PROFILING_CPU_ENABLED: bool = os.getenv("DD_PROFILING_CPU_ENABLED", "true").lower() == "true"

    # Query profiling (for DB queries)
    DD_TRACE_DATABASE_ENABLED: bool = os.getenv("DD_TRACE_DATABASE_ENABLED", "true").lower() == "true"
    DD_TRACE_ANALYTICS_SAMPLE_RATE: float = float(os.getenv("DD_TRACE_ANALYTICS_SAMPLE_RATE", "0.5"))  # 50% DB queries

    # Optional database connection
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    def __post_init__(self):
        """Validate configuration and warn about unsafe production settings."""
        # Check if API key exists (but don't fail - graceful degradation)
        if not self.DD_API_KEY:
            logger.warning("⚠️  DD_API_KEY not set - APM will be disabled")

        # Warn about unsafe profiling settings
        if self.DD_PROFILING_CAPTURE_PCT > 5:
            logger.warning(
                f"⚠️  WARNING: Profiling {self.DD_PROFILING_CAPTURE_PCT}% may impact performance. "
                f"Recommended: ≤1% for production"
            )

        # Warn about high sampling (cost control)
        if self.DD_TRACE_SAMPLE_RATE > 0.2:
            logger.warning(
                f"⚠️  WARNING: Sampling {self.DD_TRACE_SAMPLE_RATE * 100}% may increase costs significantly. "
                f"At 100K requests/day: {self._estimate_monthly_cost()} spans/month"
            )

        # FAIL on production with unsafe sampling (safety check)
        if self.DD_ENV == "production" and self.DD_TRACE_SAMPLE_RATE > 0.5:
            raise ValueError(
                f"❌ PRODUCTION SAFETY: DD_TRACE_SAMPLE_RATE={self.DD_TRACE_SAMPLE_RATE} too high. "
                f"Maximum allowed: 0.5 (50%). Recommended: 0.1 (10%)"
            )

    def _estimate_monthly_cost(self) -> str:
        """Estimate monthly span count and cost based on current config."""
        # Assume 100K requests/day, 10 spans per request average
        daily_requests = 100_000
        spans_per_request = 10
        daily_spans = daily_requests * spans_per_request * self.DD_TRACE_SAMPLE_RATE
        monthly_spans = daily_spans * 30
        cost_per_million = 5  # $5 per 1M spans
        monthly_cost = (monthly_spans / 1_000_000) * cost_per_million

        return f"{monthly_spans/1_000_000:.1f}M spans (~${monthly_cost:.0f}/month)"

    def is_enabled(self) -> bool:
        """Check if APM is enabled (has API key)."""
        return bool(self.DD_API_KEY)


def get_config() -> APMConfig:
    """Get APM configuration instance."""
    return APMConfig()


# Global config instance
apm_config = get_config()


if __name__ == "__main__":
    # Test configuration
    logging.basicConfig(level=logging.INFO)

    print(f"APM Service: {apm_config.DD_SERVICE}")
    print(f"Environment: {apm_config.DD_ENV}")
    print(f"Profiling: {apm_config.DD_PROFILING_ENABLED}")
    print(f"Sample Rate: {apm_config.DD_TRACE_SAMPLE_RATE * 100}%")
    print(f"Enabled: {apm_config.is_enabled()}")

    if apm_config.is_enabled():
        print(f"Est. Monthly Usage: {apm_config._estimate_monthly_cost()}")
