"""
Module 7.3: Custom Business Metrics for RAG Systems
===================================================

This module implements business-level observability for RAG systems,
bridging technical metrics (latency, errors) with business value
(satisfaction, feature adoption, revenue attribution).

Key concepts:
- RAG quality metrics (accuracy, satisfaction, hallucination rate)
- User cohort analysis (FREE, PAID, ENTERPRISE, etc.)
- Feature usage tracking
- Executive KPI aggregation
- Prometheus-based metric collection

Author: Level 2 Observability Module
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from prometheus_client import Counter, Gauge, Histogram, Summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class UserCohort(str, Enum):
    """User segment categories - BOUNDED to prevent cardinality explosion."""
    FREE = "free"
    PAID = "paid"
    ENTERPRISE = "enterprise"
    NEW = "new"          # First 30 days
    POWER = "power"      # >100 queries/month
    AT_RISK = "at_risk"  # No queries in 14 days


class QueryAccuracy(str, Enum):
    """RAG query outcome categories."""
    ACCURATE = "accurate"
    PARTIAL = "partial"
    INACCURATE = "inaccurate"
    HALLUCINATED = "hallucinated"


class FeatureType(str, Enum):
    """RAG feature categories."""
    SIMPLE_QA = "simple_qa"
    SUMMARIZATION = "summarization"
    MULTI_DOC = "multi_doc"
    CONVERSATIONAL = "conversational"


@dataclass
class QueryMetrics:
    """Container for a single query's business metrics."""
    query_id: str
    user_id: str
    cohort: UserCohort
    accuracy: QueryAccuracy
    satisfaction: Optional[int]  # 1-5 scale
    confidence: float            # 0.0-1.0
    feature: FeatureType
    timestamp: datetime
    latency_ms: float


# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================

# RAG Quality Metrics
query_accuracy_counter = Counter(
    'rag_query_accuracy_total',
    'Count of query outcomes by accuracy category',
    ['accuracy', 'cohort']
)

user_satisfaction_histogram = Histogram(
    'rag_user_satisfaction',
    'User satisfaction ratings (1-5 scale)',
    ['cohort', 'feature'],
    buckets=[1, 2, 3, 4, 5]
)

hallucination_rate_gauge = Gauge(
    'rag_hallucination_rate',
    'Current hallucination rate percentage',
    ['cohort']
)

model_confidence_summary = Summary(
    'rag_model_confidence',
    'Model confidence scores',
    ['feature']
)

# Cohort Analysis Metrics
cohort_queries_counter = Counter(
    'rag_cohort_queries_total',
    'Total queries per cohort',
    ['cohort', 'feature']
)

active_users_gauge = Gauge(
    'rag_active_users',
    'Current active users by cohort',
    ['cohort']
)

cohort_cost_counter = Counter(
    'rag_cohort_cost_dollars',
    'Cumulative cost per cohort in dollars',
    ['cohort']
)

# Feature Usage Metrics
feature_usage_counter = Counter(
    'rag_feature_usage_total',
    'Feature usage counts',
    ['feature', 'cohort']
)

feature_success_rate_gauge = Gauge(
    'rag_feature_success_rate',
    'Feature success rate percentage',
    ['feature']
)


# =============================================================================
# CORE METRIC TRACKING FUNCTIONS
# =============================================================================

def record_query_metrics(metrics: QueryMetrics) -> None:
    """
    Record all business metrics for a single RAG query.

    Args:
        metrics: QueryMetrics object containing all metric data

    Raises:
        ValueError: If metrics contain invalid values
    """
    try:
        # Validate inputs
        if metrics.confidence < 0.0 or metrics.confidence > 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {metrics.confidence}")

        if metrics.satisfaction and not (1 <= metrics.satisfaction <= 5):
            raise ValueError(f"Satisfaction must be 1-5, got {metrics.satisfaction}")

        # Record accuracy
        query_accuracy_counter.labels(
            accuracy=metrics.accuracy.value,
            cohort=metrics.cohort.value
        ).inc()

        # Record satisfaction if provided
        if metrics.satisfaction:
            user_satisfaction_histogram.labels(
                cohort=metrics.cohort.value,
                feature=metrics.feature.value
            ).observe(metrics.satisfaction)

        # Record confidence
        model_confidence_summary.labels(
            feature=metrics.feature.value
        ).observe(metrics.confidence)

        # Record cohort query
        cohort_queries_counter.labels(
            cohort=metrics.cohort.value,
            feature=metrics.feature.value
        ).inc()

        # Record feature usage
        feature_usage_counter.labels(
            feature=metrics.feature.value,
            cohort=metrics.cohort.value
        ).inc()

        logger.info(
            f"Recorded metrics for query {metrics.query_id}: "
            f"cohort={metrics.cohort.value}, accuracy={metrics.accuracy.value}"
        )

    except Exception as e:
        logger.error(f"Failed to record metrics for query {metrics.query_id}: {e}")
        raise


def get_user_cohort(
    user_id: str,
    user_metadata: Optional[Dict] = None
) -> UserCohort:
    """
    Determine user cohort based on metadata.
    MUST execute in <10ms per query - use Redis cache or precomputation.

    Args:
        user_id: User identifier
        user_metadata: Optional dict with user info (tier, signup_date, query_count, last_query_date)

    Returns:
        UserCohort enum value

    Note:
        In production, implement Redis caching or nightly precomputation
        to avoid database lookups on the critical path.
    """
    start_time = time.time()

    try:
        # Default metadata if none provided
        if user_metadata is None:
            logger.warning(f"No metadata for user {user_id}, defaulting to FREE")
            return UserCohort.FREE

        # Check tier first (highest priority)
        tier = user_metadata.get('tier', 'free').lower()
        if tier == 'enterprise':
            return UserCohort.ENTERPRISE
        elif tier == 'paid':
            return UserCohort.PAID

        # Check activity patterns
        days_since_signup = user_metadata.get('days_since_signup', 999)
        query_count = user_metadata.get('query_count', 0)
        days_since_last_query = user_metadata.get('days_since_last_query', 0)

        # At-risk users (14 days inactive)
        if days_since_last_query > 14:
            return UserCohort.AT_RISK

        # Power users (>100 queries/month)
        if query_count > 100:
            return UserCohort.POWER

        # New users (first 30 days)
        if days_since_signup <= 30:
            return UserCohort.NEW

        # Default to FREE
        return UserCohort.FREE

    finally:
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 10:
            logger.error(
                f"Cohort lookup for {user_id} took {elapsed_ms:.2f}ms (>10ms threshold)"
            )


def update_hallucination_rate(
    cohort: UserCohort,
    total_queries: int,
    hallucinated_queries: int
) -> float:
    """
    Calculate and update hallucination rate for a cohort.

    Args:
        cohort: User cohort
        total_queries: Total queries in time window
        hallucinated_queries: Count of hallucinated responses

    Returns:
        Hallucination rate as percentage (0-100)
    """
    try:
        if total_queries == 0:
            rate = 0.0
        else:
            rate = (hallucinated_queries / total_queries) * 100

        hallucination_rate_gauge.labels(cohort=cohort.value).set(rate)

        logger.info(f"Updated hallucination rate for {cohort.value}: {rate:.2f}%")
        return rate

    except Exception as e:
        logger.error(f"Failed to update hallucination rate: {e}")
        raise


def update_active_users(cohort: UserCohort, count: int) -> None:
    """
    Update active user count for a cohort.

    Args:
        cohort: User cohort
        count: Number of active users
    """
    try:
        active_users_gauge.labels(cohort=cohort.value).set(count)
        logger.info(f"Updated active users for {cohort.value}: {count}")
    except Exception as e:
        logger.error(f"Failed to update active users: {e}")
        raise


def record_cost(cohort: UserCohort, cost_dollars: float) -> None:
    """
    Record incremental cost for a cohort.

    Args:
        cohort: User cohort
        cost_dollars: Cost in USD
    """
    try:
        cohort_cost_counter.labels(cohort=cohort.value).inc(cost_dollars)
        logger.info(f"Recorded ${cost_dollars:.4f} cost for {cohort.value}")
    except Exception as e:
        logger.error(f"Failed to record cost: {e}")
        raise


def update_feature_success_rate(
    feature: FeatureType,
    total_uses: int,
    successful_uses: int
) -> float:
    """
    Calculate and update feature success rate.

    Args:
        feature: Feature type
        total_uses: Total usage count in time window
        successful_uses: Count of successful uses

    Returns:
        Success rate as percentage (0-100)
    """
    try:
        if total_uses == 0:
            rate = 0.0
        else:
            rate = (successful_uses / total_uses) * 100

        feature_success_rate_gauge.labels(feature=feature.value).set(rate)

        logger.info(f"Updated success rate for {feature.value}: {rate:.2f}%")
        return rate

    except Exception as e:
        logger.error(f"Failed to update feature success rate: {e}")
        raise


# =============================================================================
# EXECUTIVE KPI CALCULATIONS
# =============================================================================

def calculate_cost_per_user(
    total_cost: float,
    active_users: int
) -> Optional[float]:
    """
    Calculate cost per active user.

    Args:
        total_cost: Total infrastructure cost in USD
        active_users: Number of active users

    Returns:
        Cost per user in USD, or None if no active users
    """
    if active_users == 0:
        logger.warning("Cannot calculate cost per user: no active users")
        return None

    return total_cost / active_users


def calculate_satisfaction_trend(
    satisfaction_scores: List[float],
    window_size: int = 7
) -> Tuple[float, str]:
    """
    Calculate satisfaction trend over time.

    Args:
        satisfaction_scores: List of average satisfaction scores (oldest to newest)
        window_size: Number of days to analyze

    Returns:
        Tuple of (trend_percentage, direction) where direction is 'up', 'down', or 'stable'
    """
    if len(satisfaction_scores) < 2:
        return 0.0, 'stable'

    # Use last N scores
    recent_scores = satisfaction_scores[-window_size:]

    if len(recent_scores) < 2:
        return 0.0, 'stable'

    # Simple linear trend
    first_avg = sum(recent_scores[:len(recent_scores)//2]) / (len(recent_scores)//2)
    second_avg = sum(recent_scores[len(recent_scores)//2:]) / (len(recent_scores) - len(recent_scores)//2)

    if first_avg == 0:
        return 0.0, 'stable'

    trend_pct = ((second_avg - first_avg) / first_avg) * 100

    if abs(trend_pct) < 2:  # Less than 2% change is stable
        direction = 'stable'
    elif trend_pct > 0:
        direction = 'up'
    else:
        direction = 'down'

    return trend_pct, direction


def calculate_feature_adoption_rate(
    feature_usage_counts: Dict[str, int],
    total_queries: int
) -> Dict[str, float]:
    """
    Calculate adoption rate for each feature.

    Args:
        feature_usage_counts: Dict mapping feature name to usage count
        total_queries: Total number of queries

    Returns:
        Dict mapping feature name to adoption percentage
    """
    if total_queries == 0:
        logger.warning("Cannot calculate adoption rates: no queries")
        return {feature: 0.0 for feature in feature_usage_counts}

    return {
        feature: (count / total_queries) * 100
        for feature, count in feature_usage_counts.items()
    }


def calculate_cohort_retention_rate(
    cohort_users_start: int,
    cohort_users_end: int
) -> float:
    """
    Calculate retention rate for a cohort over a period.

    Args:
        cohort_users_start: Number of users at start of period
        cohort_users_end: Number of users at end of period

    Returns:
        Retention rate as percentage (0-100)
    """
    if cohort_users_start == 0:
        logger.warning("Cannot calculate retention: no users at start")
        return 0.0

    return (cohort_users_end / cohort_users_start) * 100


# =============================================================================
# AGGREGATION AND REPORTING
# =============================================================================

def generate_executive_summary(
    time_period: str = "last_7_days"
) -> Dict:
    """
    Generate executive KPI summary.

    Args:
        time_period: Time period for analysis

    Returns:
        Dict containing executive KPIs

    Note:
        In production, this would query Prometheus/ClickHouse for actual data.
        This implementation provides the structure and calculation logic.
    """
    logger.info(f"Generating executive summary for {time_period}")

    # In production, these would be queried from Prometheus
    # This is a template showing the structure
    summary = {
        "period": time_period,
        "generated_at": datetime.utcnow().isoformat(),
        "kpis": {
            "total_queries": 0,
            "active_users": 0,
            "avg_satisfaction": 0.0,
            "satisfaction_trend": "stable",
            "hallucination_rate": 0.0,
            "cost_per_user": 0.0,
            "feature_adoption": {},
            "cohort_metrics": {
                cohort.value: {
                    "users": 0,
                    "queries": 0,
                    "avg_satisfaction": 0.0,
                    "retention_rate": 0.0
                }
                for cohort in UserCohort
            }
        }
    }

    return summary


# =============================================================================
# COMMON FAILURE HANDLERS
# =============================================================================

def handle_cardinality_explosion(label_values: List[str], max_cardinality: int = 100) -> bool:
    """
    Check if label values would cause cardinality explosion.

    Args:
        label_values: List of label values
        max_cardinality: Maximum allowed unique values

    Returns:
        True if cardinality is safe, False if explosion risk
    """
    unique_count = len(set(label_values))

    if unique_count > max_cardinality:
        logger.error(
            f"Cardinality explosion risk: {unique_count} unique values "
            f"(max {max_cardinality})"
        )
        return False

    return True


def validate_metric_labels(labels: Dict[str, str]) -> bool:
    """
    Validate that metric labels use bounded values.

    Args:
        labels: Dict of label names to values

    Returns:
        True if labels are valid, False otherwise
    """
    # Check for unbounded identifiers
    unbounded_patterns = ['user_id', 'query_id', 'session_id', 'request_id']

    for label_name in labels.keys():
        if any(pattern in label_name.lower() for pattern in unbounded_patterns):
            logger.error(
                f"Invalid label '{label_name}': contains unbounded identifier. "
                f"Use cohorts instead of IDs."
            )
            return False

    return True


# =============================================================================
# CLI USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Module 7.3: Custom Business Metrics - CLI Examples")
    print("=" * 70)

    # Example 1: Record a query with all metrics
    print("\n[Example 1] Recording query metrics...")
    metrics = QueryMetrics(
        query_id="q123",
        user_id="u456",
        cohort=UserCohort.PAID,
        accuracy=QueryAccuracy.ACCURATE,
        satisfaction=5,
        confidence=0.92,
        feature=FeatureType.SIMPLE_QA,
        timestamp=datetime.utcnow(),
        latency_ms=245.3
    )
    record_query_metrics(metrics)
    print("✓ Metrics recorded")

    # Example 2: Determine user cohort
    print("\n[Example 2] Determining user cohort...")
    cohort = get_user_cohort(
        "u789",
        user_metadata={
            'tier': 'enterprise',
            'days_since_signup': 45,
            'query_count': 250,
            'days_since_last_query': 1
        }
    )
    print(f"✓ User cohort: {cohort.value}")

    # Example 3: Update hallucination rate
    print("\n[Example 3] Updating hallucination rate...")
    rate = update_hallucination_rate(
        cohort=UserCohort.FREE,
        total_queries=1000,
        hallucinated_queries=15
    )
    print(f"✓ Hallucination rate: {rate:.2f}%")

    # Example 4: Calculate KPIs
    print("\n[Example 4] Calculating executive KPIs...")
    cost_per_user = calculate_cost_per_user(total_cost=500.0, active_users=250)
    print(f"✓ Cost per user: ${cost_per_user:.2f}")

    adoption = calculate_feature_adoption_rate(
        feature_usage_counts={
            'simple_qa': 700,
            'summarization': 200,
            'multi_doc': 100
        },
        total_queries=1000
    )
    print(f"✓ Feature adoption: {adoption}")

    # Example 5: Generate executive summary
    print("\n[Example 5] Generating executive summary...")
    summary = generate_executive_summary()
    print(f"✓ Summary generated for period: {summary['period']}")

    print("\n" + "=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)
