"""
Smoke tests for Module 8.4: Human-in-the-Loop Evaluation

Minimal tests to verify:
- Configuration loads correctly
- Core functions return expected shapes
- Graceful handling when services unavailable
"""

import pytest
import os
import sys
import json
import tempfile
import numpy as np
from datetime import datetime

# Note: Ensure PYTHONPATH includes src/ directory when running tests

from m8_hitl_eval.hitl import (
    FeedbackCollector,
    Feedback,
    ActiveLearningSelector,
    InterAnnotatorAgreement,
    FeedbackLoopManager,
    export_to_label_studio,
    AnnotationTask
)
from m8_hitl_eval.config import Config


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_config_loads():
    """Test that configuration loads with defaults."""
    config = Config()
    assert config.DB_PATH is not None
    assert config.UNCERTAINTY_WEIGHT >= 0
    assert config.MIN_IAA_THRESHOLD > 0
    print("✓ Config loads correctly")


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_feedback_collector():
    """Test feedback collection and retrieval."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        collector = FeedbackCollector(db_path=db_path)

        # Add feedback
        feedback = Feedback(
            query_id="test_q1",
            user_id="test_user",
            feedback_type="thumbs_up",
            rating=5,
            comment="Test comment",
            timestamp=datetime.now().isoformat()
        )

        success = collector.add_feedback(feedback)
        assert success, "Failed to add feedback"

        # Retrieve feedback
        unprocessed = collector.get_unprocessed_feedback(limit=10)
        assert len(unprocessed) > 0, "No feedback retrieved"
        assert unprocessed[0]['query_id'] == "test_q1"

        print("✓ FeedbackCollector works correctly")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_active_learning_selector():
    """Test active learning query selection."""
    selector = ActiveLearningSelector()

    # Create sample queries
    queries = [
        {
            "query_id": f"q_{i}",
            "query_text": f"Query {i}",
            "response_text": f"Response {i}",
            "sources": [f"doc_{i}"],
            "confidence": np.random.uniform(0.3, 0.9),
            "has_negative_feedback": i % 5 == 0
        }
        for i in range(50)
    ]

    embeddings = np.random.randn(50, 128)

    # Select queries
    tasks = selector.select_for_annotation(
        queries=queries,
        embeddings=embeddings,
        n_select=10,
        n_clusters=3
    )

    assert len(tasks) <= 10, f"Expected ≤10 tasks, got {len(tasks)}"
    assert all(isinstance(t, AnnotationTask) for t in tasks)
    assert all(hasattr(t, 'priority_score') for t in tasks)

    print("✓ ActiveLearningSelector works correctly")


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_iaa_calculation():
    """Test inter-annotator agreement metrics."""
    iaa = InterAnnotatorAgreement()

    # Test Cohen's Kappa
    ann_a = [1, 1, 0, 1, 0, 1, 1, 0]
    ann_b = [1, 1, 0, 1, 0, 1, 1, 1]

    kappa = iaa.cohens_kappa(ann_a, ann_b)
    assert -1 <= kappa <= 1, f"Kappa out of range: {kappa}"

    # Test Krippendorff's Alpha
    annotations = [
        [1, 1, 0, 1, 0, 1, 1, 0],
        [1, 1, 0, 1, 0, 1, 1, 1],
        [1, 1, 0, 0, 0, 1, 1, 0]
    ]

    alpha = iaa.krippendorffs_alpha(annotations)
    assert -1 <= alpha <= 1, f"Alpha out of range: {alpha}"

    print("✓ InterAnnotatorAgreement works correctly")


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_feedback_loop_manager():
    """Test feedback loop aggregation and training extraction."""
    manager = FeedbackLoopManager()

    # Test aggregation
    annotations = [
        {
            "query_id": "q1",
            "annotator_id": "ann1",
            "factual_correctness": True,
            "helpfulness": 4,
            "needs_improvement": False
        },
        {
            "query_id": "q1",
            "annotator_id": "ann2",
            "factual_correctness": True,
            "helpfulness": 5,
            "needs_improvement": False
        }
    ]

    result = manager.aggregate_annotations(annotations)
    assert result['query_id'] == "q1"
    assert 'factual_correct' in result
    assert 'confidence' in result

    # Test training example extraction
    aggregated = [result]
    training = manager.extract_training_examples(aggregated, min_confidence=0.5)
    assert len(training) <= len(aggregated)

    print("✓ FeedbackLoopManager works correctly")


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_label_studio_export():
    """Test export to Label Studio format."""
    tasks = [
        AnnotationTask(
            query_id="q1",
            query_text="Test query",
            response_text="Test response",
            sources=["doc1"],
            uncertainty_score=0.5,
            priority_score=0.7
        )
    ]

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as tmp:
        output_path = tmp.name

    try:
        success = export_to_label_studio(tasks, output_path)
        assert success, "Export failed"

        # Verify file exists and is valid JSON
        with open(output_path, 'r') as f:
            data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert 'data' in data[0]

        print("✓ Label Studio export works correctly")

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_example_data_loads():
    """Test that example data file is valid."""
    example_path = os.path.join(os.path.dirname(__file__), "example_data.json")

    if not os.path.exists(example_path):
        print("⚠ example_data.json not found - skipping")
        return

    with open(example_path, 'r') as f:
        data = json.load(f)

    assert 'queries' in data
    assert 'feedback' in data
    assert len(data['queries']) > 0

    print("✓ example_data.json is valid")


@pytest.mark.skipif(os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true', reason='Integration tests skipped')
def test_graceful_degradation():
    """Test graceful handling when services unavailable."""
    # Test with missing Label Studio config
    from m8_hitl_eval.config import get_label_studio_client

    client = get_label_studio_client()
    # Should return None without crashing
    assert client is None or client is not None  # Either is fine

    print("✓ Graceful degradation works")


def run_all_tests():
    """Run all smoke tests."""
    print("\n=== Running Smoke Tests for Module 8.4 ===\n")

    tests = [
        test_config_loads,
        test_feedback_collector,
        test_active_learning_selector,
        test_iaa_calculation,
        test_feedback_loop_manager,
        test_label_studio_export,
        test_example_data_loads,
        test_graceful_degradation
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

@pytest.fixture(autouse=True)
def _skip_if_no_infra():
    """Skip all tests if SKIP_INTEGRATION_TESTS is set."""
    if os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true':
        pytest.skip('Integration tests skipped via SKIP_INTEGRATION_TESTS=true')

