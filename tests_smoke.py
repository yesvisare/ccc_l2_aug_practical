"""
Smoke tests for Module 7.3: Custom Business Metrics
===================================================

Basic tests to ensure:
- Configuration loads correctly
- Core functions return expected types
- Graceful handling when external services unavailable
"""

import json
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

# Import modules to test
import config
import l2_m7_custom_business_metrics as metrics_module
from app import app


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

def test_config_loads():
    """Test that configuration loads without errors."""
    cfg = config.load_config()

    assert cfg is not None
    assert hasattr(cfg, 'prometheus')
    assert hasattr(cfg, 'redis')
    assert hasattr(cfg, 'clickhouse')
    assert hasattr(cfg, 'metrics')


def test_config_defaults():
    """Test that configuration has sensible defaults."""
    cfg = config.load_config()

    # Prometheus should be enabled by default
    assert cfg.prometheus.enabled is True
    assert cfg.prometheus.port > 0

    # Metrics thresholds should be set
    assert cfg.metrics.cohort_lookup_max_ms > 0
    assert cfg.metrics.max_label_cardinality > 0
    assert 1 <= cfg.metrics.satisfaction_min <= cfg.metrics.satisfaction_max <= 5


def test_get_clients_graceful_failure():
    """Test that get_clients returns None for unavailable services without crashing."""
    clients = config.get_clients()

    assert 'redis' in clients
    assert 'clickhouse' in clients
    # Services may be None if not available - that's expected


# =============================================================================
# CORE METRICS TESTS
# =============================================================================

def test_user_cohort_determination():
    """Test that user cohort is determined correctly."""
    # Enterprise user
    cohort = metrics_module.get_user_cohort(
        "u001",
        {"tier": "enterprise", "days_since_signup": 100, "query_count": 500, "days_since_last_query": 1}
    )
    assert cohort == metrics_module.UserCohort.ENTERPRISE

    # New user
    cohort = metrics_module.get_user_cohort(
        "u002",
        {"tier": "free", "days_since_signup": 10, "query_count": 5, "days_since_last_query": 0}
    )
    assert cohort == metrics_module.UserCohort.NEW

    # Power user
    cohort = metrics_module.get_user_cohort(
        "u003",
        {"tier": "free", "days_since_signup": 60, "query_count": 150, "days_since_last_query": 1}
    )
    assert cohort == metrics_module.UserCohort.POWER

    # At-risk user
    cohort = metrics_module.get_user_cohort(
        "u004",
        {"tier": "paid", "days_since_signup": 200, "query_count": 80, "days_since_last_query": 20}
    )
    assert cohort == metrics_module.UserCohort.AT_RISK


def test_record_query_metrics():
    """Test that query metrics can be recorded without errors."""
    test_metrics = metrics_module.QueryMetrics(
        query_id="test_q001",
        user_id="test_u001",
        cohort=metrics_module.UserCohort.FREE,
        accuracy=metrics_module.QueryAccuracy.ACCURATE,
        satisfaction=4,
        confidence=0.85,
        feature=metrics_module.FeatureType.SIMPLE_QA,
        timestamp=datetime.utcnow(),
        latency_ms=200.0
    )

    # Should not raise exception
    metrics_module.record_query_metrics(test_metrics)


def test_record_query_metrics_validation():
    """Test that invalid metrics are rejected."""
    # Invalid confidence (>1.0)
    with pytest.raises(ValueError):
        test_metrics = metrics_module.QueryMetrics(
            query_id="test_q002",
            user_id="test_u002",
            cohort=metrics_module.UserCohort.FREE,
            accuracy=metrics_module.QueryAccuracy.ACCURATE,
            satisfaction=4,
            confidence=1.5,  # Invalid
            feature=metrics_module.FeatureType.SIMPLE_QA,
            timestamp=datetime.utcnow(),
            latency_ms=200.0
        )
        metrics_module.record_query_metrics(test_metrics)

    # Invalid satisfaction (>5)
    with pytest.raises(ValueError):
        test_metrics = metrics_module.QueryMetrics(
            query_id="test_q003",
            user_id="test_u003",
            cohort=metrics_module.UserCohort.FREE,
            accuracy=metrics_module.QueryAccuracy.ACCURATE,
            satisfaction=6,  # Invalid
            confidence=0.85,
            feature=metrics_module.FeatureType.SIMPLE_QA,
            timestamp=datetime.utcnow(),
            latency_ms=200.0
        )
        metrics_module.record_query_metrics(test_metrics)


def test_hallucination_rate_calculation():
    """Test hallucination rate calculation."""
    rate = metrics_module.update_hallucination_rate(
        cohort=metrics_module.UserCohort.FREE,
        total_queries=100,
        hallucinated_queries=5
    )

    assert rate == 5.0

    # Edge case: zero queries
    rate = metrics_module.update_hallucination_rate(
        cohort=metrics_module.UserCohort.PAID,
        total_queries=0,
        hallucinated_queries=0
    )

    assert rate == 0.0


def test_feature_success_rate_calculation():
    """Test feature success rate calculation."""
    rate = metrics_module.update_feature_success_rate(
        feature=metrics_module.FeatureType.SIMPLE_QA,
        total_uses=100,
        successful_uses=85
    )

    assert rate == 85.0

    # Edge case: zero uses
    rate = metrics_module.update_feature_success_rate(
        feature=metrics_module.FeatureType.SUMMARIZATION,
        total_uses=0,
        successful_uses=0
    )

    assert rate == 0.0


# =============================================================================
# KPI CALCULATION TESTS
# =============================================================================

def test_cost_per_user_calculation():
    """Test cost per user KPI."""
    cpu = metrics_module.calculate_cost_per_user(total_cost=500.0, active_users=100)
    assert cpu == 5.0

    # Edge case: no users
    cpu = metrics_module.calculate_cost_per_user(total_cost=500.0, active_users=0)
    assert cpu is None


def test_satisfaction_trend_calculation():
    """Test satisfaction trend detection."""
    # Upward trend
    scores = [3.0, 3.2, 3.5, 3.8, 4.0, 4.2, 4.5]
    trend, direction = metrics_module.calculate_satisfaction_trend(scores)
    assert direction == 'up'

    # Downward trend
    scores = [4.5, 4.2, 4.0, 3.8, 3.5, 3.2, 3.0]
    trend, direction = metrics_module.calculate_satisfaction_trend(scores)
    assert direction == 'down'

    # Stable
    scores = [4.0, 4.0, 4.1, 3.9, 4.0, 4.0, 4.0]
    trend, direction = metrics_module.calculate_satisfaction_trend(scores)
    assert direction == 'stable'


def test_feature_adoption_rate_calculation():
    """Test feature adoption rate calculation."""
    usage = {
        'simple_qa': 700,
        'summarization': 200,
        'multi_doc': 100
    }

    rates = metrics_module.calculate_feature_adoption_rate(usage, 1000)

    assert rates['simple_qa'] == 70.0
    assert rates['summarization'] == 20.0
    assert rates['multi_doc'] == 10.0


def test_cohort_retention_rate_calculation():
    """Test cohort retention rate."""
    rate = metrics_module.calculate_cohort_retention_rate(
        cohort_users_start=100,
        cohort_users_end=85
    )

    assert rate == 85.0

    # Edge case: no users at start
    rate = metrics_module.calculate_cohort_retention_rate(
        cohort_users_start=0,
        cohort_users_end=0
    )

    assert rate == 0.0


def test_executive_summary_structure():
    """Test that executive summary has correct structure."""
    summary = metrics_module.generate_executive_summary()

    assert 'period' in summary
    assert 'generated_at' in summary
    assert 'kpis' in summary

    kpis = summary['kpis']
    assert 'total_queries' in kpis
    assert 'active_users' in kpis
    assert 'avg_satisfaction' in kpis
    assert 'cohort_metrics' in kpis


# =============================================================================
# FAILURE HANDLING TESTS
# =============================================================================

def test_cardinality_explosion_detection():
    """Test cardinality explosion detection."""
    # Safe cardinality
    safe_labels = [f"label_{i}" for i in range(50)]
    assert metrics_module.handle_cardinality_explosion(safe_labels, max_cardinality=100) is True

    # Unsafe cardinality
    unsafe_labels = [f"label_{i}" for i in range(150)]
    assert metrics_module.handle_cardinality_explosion(unsafe_labels, max_cardinality=100) is False


def test_label_validation():
    """Test metric label validation."""
    # Valid labels (bounded)
    valid_labels = {
        'cohort': 'paid',
        'feature': 'simple_qa',
        'accuracy': 'accurate'
    }
    assert metrics_module.validate_metric_labels(valid_labels) is True

    # Invalid labels (unbounded)
    invalid_labels = {
        'user_id': 'u12345',
        'feature': 'simple_qa'
    }
    assert metrics_module.validate_metric_labels(invalid_labels) is False


# =============================================================================
# API TESTS
# =============================================================================

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data['status'] == 'ok'
    assert 'timestamp' in data
    assert 'services' in data


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert 'service' in data
    assert 'version' in data
    assert 'endpoints' in data


def test_record_query_endpoint():
    """Test query recording endpoint."""
    payload = {
        "query_id": "test_q100",
        "user_id": "test_u100",
        "user_metadata": {
            "tier": "paid",
            "days_since_signup": 60,
            "query_count": 120,
            "days_since_last_query": 1
        },
        "accuracy": "accurate",
        "satisfaction": 5,
        "confidence": 0.92,
        "feature": "simple_qa",
        "latency_ms": 234.5
    }

    response = client.post("/metrics/query", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data['status'] == 'recorded'
    assert data['query_id'] == 'test_q100'
    assert 'cohort' in data


def test_record_query_endpoint_validation():
    """Test query endpoint validation."""
    # Invalid accuracy
    payload = {
        "query_id": "test_q101",
        "user_id": "test_u101",
        "accuracy": "invalid_accuracy",  # Invalid
        "confidence": 0.92,
        "feature": "simple_qa",
        "latency_ms": 234.5
    }

    response = client.post("/metrics/query", json=payload)
    assert response.status_code == 422  # Validation error


def test_kpi_summary_endpoint():
    """Test KPI summary endpoint."""
    payload = {
        "time_period": "last_7_days"
    }

    response = client.post("/kpi/summary", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert 'period' in data
    assert 'kpis' in data


def test_prometheus_metrics_endpoint():
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'text/plain' in response.headers['content-type']


# =============================================================================
# EXAMPLE DATA TESTS
# =============================================================================

def test_example_data_loads():
    """Test that example data file is valid JSON."""
    example_file = os.path.join(os.path.dirname(__file__), 'example_data.json')

    assert os.path.exists(example_file), "example_data.json not found"

    with open(example_file, 'r') as f:
        data = json.load(f)

    assert 'queries' in data
    assert 'cohort_summary' in data
    assert 'feature_usage' in data
    assert 'kpi_baseline' in data

    # Validate query structure
    if data['queries']:
        query = data['queries'][0]
        assert 'query_id' in query
        assert 'user_id' in query
        assert 'accuracy' in query
        assert 'confidence' in query


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
