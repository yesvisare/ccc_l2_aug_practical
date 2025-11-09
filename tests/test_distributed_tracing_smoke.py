"""
Smoke tests for Module 7.1: Distributed Tracing with OpenTelemetry

Tests basic functionality:
- Configuration loads correctly
- Tracer initializes without errors
- Core functions return expected shapes
- Network paths gracefully skip without Jaeger
- FastAPI endpoints respond correctly

Run with: pytest tests_smoke.py -v
Set SKIP_INTEGRATION_TESTS=true to skip tests requiring dependencies.
"""

import pytest
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Skip all tests if SKIP_INTEGRATION_TESTS is set or dependencies missing
skip_integration = os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true'

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import m7_distributed_tracing.config
        import m7_distributed_tracing.tracing
        return True
    except ImportError:
        return False

skip_reason = None
if skip_integration:
    skip_reason = "SKIP_INTEGRATION_TESTS=true"
elif not check_dependencies():
    skip_reason = "Missing dependencies (install requirements.txt)"

# Apply skip marker to entire module if needed
if skip_reason:
    pytestmark = pytest.mark.skip(reason=skip_reason)

# Test imports work
def test_imports():
    """Test that all required modules can be imported."""
    try:
        import m7_distributed_tracing.tracing
        import m7_distributed_tracing.config
        import app
        assert m7_distributed_tracing.tracing is not None
        assert m7_distributed_tracing.config is not None
        assert app is not None
    except ImportError as e:
        pytest.skip(f"Missing dependencies: {e}")


def test_config_loads():
    """Test that configuration loads without errors."""
    from m7_distributed_tracing.config import TracingConfig, AppConfig, get_tracing_config, get_app_config

    # Test config classes exist
    assert TracingConfig is not None
    assert AppConfig is not None

    # Test config getters
    tracing_config = get_tracing_config()
    app_config = get_app_config()

    assert tracing_config.SERVICE_NAME is not None
    assert app_config.APP_NAME is not None

    # Test sampling rate is valid
    assert 0.0 <= tracing_config.SAMPLING_RATE <= 1.0

    # Test environment-specific sampling rates
    assert TracingConfig.get_sampling_rate_for_env("development") == 1.0
    assert TracingConfig.get_sampling_rate_for_env("staging") == 0.5
    assert TracingConfig.get_sampling_rate_for_env("production") == 0.1


def test_config_validation():
    """Test configuration validation."""
    from m7_distributed_tracing.config import validate_config

    results = validate_config()

    assert isinstance(results, dict)
    assert "tracing_enabled" in results
    assert "valid_sampling_rate" in results
    assert "otlp_endpoint_configured" in results
    assert "jaeger_reachable" in results

    # Sampling rate should be valid
    assert results["valid_sampling_rate"] is True


def test_tracer_initialization():
    """Test that tracer can be initialized without errors."""
    from m7_distributed_tracing.tracing import setup_tracing

    # Initialize with test config (won't export if Jaeger unavailable)
    tracer = setup_tracing(
        service_name="test-service",
        environment="test",
        sampling_rate=0.1,
        otlp_endpoint="http://localhost:4317"
    )

    assert tracer is not None
    # Tracer should be initialized even if Jaeger is unavailable (graceful degradation)


def test_trace_context_formatter():
    """Test TraceContextLogger formatter."""
    from m7_distributed_tracing.tracing import TraceContextLogger
    import logging

    formatter = TraceContextLogger()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None
    )

    formatted = formatter.format(record)
    assert isinstance(formatted, str)
    # Should have trace_id and span_id attributes (may be None if no active span)
    assert hasattr(record, 'trace_id')
    assert hasattr(record, 'span_id')


def test_redact_sensitive_attributes():
    """Test PII redaction in span attributes."""
    from m7_distributed_tracing.tracing import redact_sensitive_attributes

    attributes = {
        "question": "What is GDPR?",
        "api_key": "sk-1234567890",
        "password": "secret123",
        "user_id": "user-123",
        "token": "abc123",
        "normal_field": "value"
    }

    redacted = redact_sensitive_attributes(attributes)

    # Sensitive fields should be redacted
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"

    # Normal fields should be preserved
    assert redacted["question"] == "What is GDPR?"
    assert redacted["user_id"] == "user-123"
    assert redacted["normal_field"] == "value"


def test_simulate_retrieve_documents():
    """Test document retrieval simulation."""
    from m7_distributed_tracing.tracing import setup_tracing, simulate_retrieve_documents

    tracer = setup_tracing(service_name="test", sampling_rate=0.0)  # No sampling for test

    results = simulate_retrieve_documents(
        tracer=tracer,
        question="What is GDPR?",
        top_k=5,
        simulate_latency_ms=10  # Fast for testing
    )

    assert isinstance(results, list)
    assert len(results) == 5
    assert all("id" in doc for doc in results)
    assert all("score" in doc for doc in results)
    assert all("text" in doc for doc in results)


def test_simulate_rerank_results():
    """Test reranking simulation."""
    from m7_distributed_tracing.tracing import setup_tracing, simulate_rerank_results

    tracer = setup_tracing(service_name="test", sampling_rate=0.0)

    docs = [{"id": f"doc_{i}", "score": 0.9 - i * 0.1, "text": f"Doc {i}"} for i in range(10)]

    reranked = simulate_rerank_results(
        tracer=tracer,
        results=docs,
        question="What is GDPR?",
        top_n=3,
        simulate_latency_ms=10
    )

    assert isinstance(reranked, list)
    assert len(reranked) == 3


def test_simulate_generate_response():
    """Test LLM generation simulation."""
    from m7_distributed_tracing.tracing import setup_tracing, simulate_generate_response

    tracer = setup_tracing(service_name="test", sampling_rate=0.0)

    docs = [{"id": "doc_1", "text": "GDPR is a regulation..."}]

    result = simulate_generate_response(
        tracer=tracer,
        question="What is GDPR?",
        context_docs=docs,
        model="gpt-4",
        simulate_latency_ms=10
    )

    assert isinstance(result, dict)
    assert "response" in result
    assert "tokens" in result
    assert "cost_usd" in result
    assert "model" in result
    assert result["model"] == "gpt-4"
    assert result["tokens"] > 0
    assert result["cost_usd"] > 0


def test_process_rag_query():
    """Test full RAG pipeline."""
    from m7_distributed_tracing.tracing import setup_tracing, process_rag_query

    tracer = setup_tracing(service_name="test", sampling_rate=0.0)

    result = process_rag_query(
        tracer=tracer,
        question="What is GDPR compliance?",
        top_k=5,
        top_n=3,
        model="gpt-4"
    )

    assert isinstance(result, dict)
    assert "question" in result
    assert "response" in result
    assert "total_time_ms" in result
    assert "retrieved_count" in result
    assert "reranked_count" in result
    assert "tokens" in result
    assert "cost_usd" in result
    assert "model" in result

    assert result["retrieved_count"] == 5
    assert result["reranked_count"] == 3
    assert result["total_time_ms"] > 0


def test_get_trace_context():
    """Test trace context retrieval."""
    from m7_distributed_tracing.tracing import get_trace_context

    context = get_trace_context()

    assert isinstance(context, dict)
    assert "trace_id" in context
    assert "span_id" in context
    # May be None if no active span
    assert context["trace_id"] is None or isinstance(context["trace_id"], str)


def test_example_data_loads():
    """Test that example data file is valid JSON."""
    with open("example_data.json", "r") as f:
        data = json.load(f)

    assert "sample_queries" in data
    assert "trace_examples" in data
    assert "failure_scenarios" in data
    assert "sampling_recommendations" in data
    assert "cost_estimates" in data
    assert "jaeger_setup" in data

    # Validate sample queries structure
    assert len(data["sample_queries"]) > 0
    for query in data["sample_queries"]:
        assert "question" in query
        assert "expected_trace_stages" in query


# FastAPI tests
@pytest.fixture
def client():
    """Create test client."""
    from fastapi.testclient import TestClient
    from app import app

    return TestClient(app)


def test_health_endpoint(client):
    """Test /health endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] == "ok"
    assert "tracing_enabled" in data
    assert "tracing_available" in data
    assert "config" in data


def test_config_endpoint(client):
    """Test /config endpoint."""
    response = client.get("/config")

    assert response.status_code == 200
    data = response.json()

    assert "tracing" in data
    assert "app" in data
    assert "validation" in data


def test_query_endpoint(client):
    """Test /query endpoint."""
    request_data = {
        "question": "What are GDPR compliance requirements?",
        "top_k": 5,
        "top_n": 3,
        "model": "gpt-4"
    }

    response = client.post("/query", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "question" in data
    assert "response" in data
    assert "total_time_ms" in data
    assert "retrieved_count" in data
    assert "reranked_count" in data
    assert "tokens" in data
    assert "cost_usd" in data
    assert "model" in data
    assert "trace_id" in data
    assert "span_id" in data

    assert data["retrieved_count"] == 5
    assert data["reranked_count"] == 3


def test_query_endpoint_with_defaults(client):
    """Test /query endpoint with default parameters."""
    request_data = {
        "question": "What is HIPAA?"
    }

    response = client.post("/query", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert data["question"] == "What is HIPAA?"
    assert "response" in data


def test_trace_context_endpoint(client):
    """Test /trace/current endpoint."""
    response = client.get("/trace/current")

    assert response.status_code == 200
    data = response.json()

    assert "trace_id" in data
    assert "span_id" in data
    assert "jaeger_ui_url" in data


def test_openapi_docs(client):
    """Test that OpenAPI docs are available."""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200


# Integration test (requires Jaeger)
@pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "true").lower() == "true",
    reason="Integration tests skipped (set SKIP_INTEGRATION_TESTS=false to run)"
)
def test_jaeger_integration():
    """
    Integration test with actual Jaeger instance.

    Requires Jaeger running on localhost:4317.
    Run with: SKIP_INTEGRATION_TESTS=false pytest tests_smoke.py::test_jaeger_integration -v
    """
    from m7_distributed_tracing.tracing import setup_tracing, process_rag_query
    import time

    tracer = setup_tracing(
        service_name="test-integration",
        sampling_rate=1.0,
        otlp_endpoint="http://localhost:4317"
    )

    # Process query
    result = process_rag_query(
        tracer=tracer,
        question="Integration test query",
        top_k=5,
        top_n=3
    )

    # Wait for export
    time.sleep(6)  # BatchSpanProcessor exports every 5 seconds

    # Verify result
    assert result["retrieved_count"] == 5
    assert result["reranked_count"] == 3

    print("\n✅ Integration test passed!")
    print(f"Check Jaeger UI: http://localhost:16686")
    print(f"Service: test-integration")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
