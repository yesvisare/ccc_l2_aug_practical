"""
Module 7.3: Custom Business Metrics for RAG Systems
===================================================

This package implements business-level observability for RAG systems,
bridging technical metrics (latency, errors) with business value
(satisfaction, feature adoption, revenue attribution).
"""

from .core import (
    UserCohort,
    QueryAccuracy,
    FeatureType,
    QueryMetrics,
    record_query_metrics,
    get_user_cohort,
    update_hallucination_rate,
    update_active_users,
    record_cost,
    update_feature_success_rate,
    calculate_cost_per_user,
    calculate_satisfaction_trend,
    calculate_feature_adoption_rate,
    calculate_cohort_retention_rate,
    generate_executive_summary,
    handle_cardinality_explosion,
    validate_metric_labels,
)

from .config import (
    load_config,
    get_redis_client,
    get_clickhouse_client,
    get_clients,
)

__all__ = [
    # Enums
    "UserCohort",
    "QueryAccuracy",
    "FeatureType",
    # Data classes
    "QueryMetrics",
    # Core functions
    "record_query_metrics",
    "get_user_cohort",
    "update_hallucination_rate",
    "update_active_users",
    "record_cost",
    "update_feature_success_rate",
    # KPI calculations
    "calculate_cost_per_user",
    "calculate_satisfaction_trend",
    "calculate_feature_adoption_rate",
    "calculate_cohort_retention_rate",
    "generate_executive_summary",
    # Validation
    "handle_cardinality_explosion",
    "validate_metric_labels",
    # Config
    "load_config",
    "get_redis_client",
    "get_clickhouse_client",
    "get_clients",
]

__version__ = "1.0.0"
