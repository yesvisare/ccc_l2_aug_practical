"""
Smoke tests for Module 8.3: Regression Testing & CI/CD

Minimal tests to verify:
- Configuration loads correctly
- Core functions return expected shapes
- Network paths gracefully skip without keys
"""

import pytest
import sys
import os
from pathlib import Path
import json

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import m8_regression_cicd.regression as reg_test
import m8_regression_cicd.config as config

# Skip guard for integration tests
skip_integration = pytest.mark.skipif(
    os.getenv('SKIP_INTEGRATION_TESTS', '').lower() == 'true',
    reason="Integration tests skipped via SKIP_INTEGRATION_TESTS=true"
)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

def test_config_loads():
    """Test that configuration loads without errors."""
    assert config.FAITHFULNESS_THRESHOLD == 0.75
    assert config.ANSWER_RELEVANCY_THRESHOLD == 0.70
    assert config.CONTEXT_PRECISION_THRESHOLD == 0.65
    assert config.P95_LATENCY_THRESHOLD_MS == 2000
    assert config.COST_PER_QUERY_THRESHOLD == 0.01


def test_config_info_structure():
    """Test that config info returns expected structure."""
    info = config.get_config_info()
    assert 'test_config' in info
    assert 'thresholds' in info
    assert 'ci_cd' in info
    assert info['test_config']['subset_size'] == 50


def test_config_validation():
    """Test configuration validation returns dict."""
    validation = config.validate_config()
    assert isinstance(validation, dict)
    assert 'openai' in validation
    assert 'aws_s3' in validation


# ============================================================================
# REGRESSION METRICS TESTS
# ============================================================================

def test_regression_metrics_creation():
    """Test RegressionMetrics dataclass creation."""
    metrics = reg_test.RegressionMetrics(
        faithfulness=0.80,
        answer_relevancy=0.75,
        context_precision=0.70,
        p95_latency_ms=1500,
        cost_per_query=0.008
    )

    assert metrics.faithfulness == 0.80
    assert metrics.answer_relevancy == 0.75
    assert metrics.cost_per_query == 0.008


def test_regression_metrics_thresholds_pass():
    """Test that good metrics pass thresholds."""
    metrics = reg_test.RegressionMetrics(
        faithfulness=0.80,
        answer_relevancy=0.75,
        context_precision=0.70,
        p95_latency_ms=1500,
        cost_per_query=0.008
    )

    passes, failures = metrics.passes_thresholds()
    assert passes is True
    assert len(failures) == 0


def test_regression_metrics_thresholds_fail():
    """Test that bad metrics fail thresholds."""
    metrics = reg_test.RegressionMetrics(
        faithfulness=0.60,  # Below 0.75 threshold
        answer_relevancy=0.65,  # Below 0.70 threshold
        context_precision=0.60,  # Below 0.65 threshold
        p95_latency_ms=3000,  # Above 2000ms threshold
        cost_per_query=0.02  # Above $0.01 threshold
    )

    passes, failures = metrics.passes_thresholds()
    assert passes is False
    assert len(failures) == 5  # All metrics should fail


# ============================================================================
# REGRESSION TEST SUITE TESTS
# ============================================================================

def test_regression_test_suite_creation():
    """Test creating regression test suite."""
    test_data = [
        {
            'question': f'Question {i}',
            'expected_answer': f'Answer {i}',
            'contexts': [f'Context {i}']
        }
        for i in range(100)
    ]

    # Test with subset
    suite = reg_test.RegressionTestSuite(test_data, use_subset=True)
    assert len(suite.test_data) == 50  # Should use 50-question subset

    # Test with full set
    suite_full = reg_test.RegressionTestSuite(test_data, use_subset=False)
    assert len(suite_full.test_data) == 100


def test_regression_test_suite_empty_data():
    """Test that empty test data raises error."""
    suite = reg_test.RegressionTestSuite([], use_subset=True)

    # Mock pipeline
    class MockPipeline:
        def query(self, question):
            return {'answer': 'test', 'contexts': ['test']}

    with pytest.raises(ValueError, match="Test data is empty"):
        suite.run_quality_tests(MockPipeline())


# ============================================================================
# FLAKY TEST HANDLER TESTS
# ============================================================================

def test_flaky_test_handler_creation():
    """Test creating flaky test handler."""
    handler = reg_test.FlakyTestHandler(num_runs=5, tolerance_pct=20.0)
    assert handler.num_runs == 5
    assert handler.tolerance_pct == 20.0


def test_flaky_test_handler_stability():
    """Test running test multiple times returns median."""
    handler = reg_test.FlakyTestHandler(num_runs=5, tolerance_pct=20.0)

    def mock_test():
        return 0.75

    median, all_values = handler.run_stable_test(mock_test)
    assert median == 0.75
    assert len(all_values) == 5
    assert all(v == 0.75 for v in all_values)


def test_flaky_test_handler_baseline_check():
    """Test baseline tolerance checking."""
    handler = reg_test.FlakyTestHandler(num_runs=5, tolerance_pct=20.0)

    # Within tolerance
    assert handler.is_within_baseline(0.85, 1.00) is True  # -15%
    assert handler.is_within_baseline(1.15, 1.00) is True  # +15%

    # Outside tolerance
    assert handler.is_within_baseline(0.75, 1.00) is False  # -25%
    assert handler.is_within_baseline(1.25, 1.00) is False  # +25%


# ============================================================================
# THRESHOLD CALIBRATOR TESTS
# ============================================================================

def test_threshold_calibrator_creation(tmp_path):
    """Test creating threshold calibrator."""
    baseline_file = tmp_path / "baseline_test.json"
    calibrator = reg_test.ThresholdCalibrator(baseline_file)
    assert calibrator.baseline_file == baseline_file
    assert isinstance(calibrator.baselines, dict)


def test_threshold_calibrator_add_measurement(tmp_path):
    """Test adding measurements to calibrator."""
    baseline_file = tmp_path / "baseline_test.json"
    calibrator = reg_test.ThresholdCalibrator(baseline_file)

    calibrator.add_measurement('faithfulness', 0.80)
    calibrator.add_measurement('faithfulness', 0.82)

    assert 'faithfulness' in calibrator.baselines
    assert len(calibrator.baselines['faithfulness']) == 2


def test_threshold_calibrator_insufficient_data(tmp_path):
    """Test that insufficient data returns None."""
    baseline_file = tmp_path / "baseline_test.json"
    calibrator = reg_test.ThresholdCalibrator(baseline_file)

    # Add only 5 measurements (need ≥10)
    for i in range(5):
        calibrator.add_measurement('faithfulness', 0.80)

    threshold = calibrator.calculate_threshold('faithfulness')
    assert threshold is None  # Insufficient data


def test_threshold_calibrator_calculation(tmp_path):
    """Test threshold calculation with sufficient data."""
    baseline_file = tmp_path / "baseline_test.json"
    calibrator = reg_test.ThresholdCalibrator(baseline_file)

    # Add 15 measurements
    for i in range(15):
        calibrator.add_measurement('faithfulness', 0.80 + (i % 5) * 0.01)

    threshold = calibrator.calculate_threshold('faithfulness', num_std=2.0)
    assert threshold is not None
    assert isinstance(threshold, float)
    assert 0.5 < threshold < 1.0  # Reasonable range


# ============================================================================
# DVC VERSION MANAGER TESTS
# ============================================================================

def test_dvc_version_manager_creation(tmp_path):
    """Test creating DVC version manager."""
    models_dir = tmp_path / "models"
    manager = reg_test.DVCVersionManager(models_dir=models_dir)

    assert manager.models_dir.exists()  # Should create directory


def test_dvc_list_versions_no_git(tmp_path):
    """Test listing versions returns empty list without git."""
    models_dir = tmp_path / "models"
    manager = reg_test.DVCVersionManager(models_dir=models_dir)

    versions = manager.list_versions()
    assert isinstance(versions, list)


# ============================================================================
# DECISION HELPER TESTS
# ============================================================================

def test_should_use_cicd_small_team():
    """Test decision helper for small team."""
    should_use, reason = reg_test.should_use_cicd(
        deploys_per_month=3,
        team_size=2,
        budget_per_month=100,
        has_pmf=True
    )
    assert should_use is False
    assert "Deploy <5 times/month" in reason


def test_should_use_cicd_ideal_fit():
    """Test decision helper for ideal fit."""
    should_use, reason = reg_test.should_use_cicd(
        deploys_per_month=50,
        team_size=5,
        budget_per_month=300,
        has_pmf=True
    )
    assert should_use is True
    assert "Ideal fit" in reason or "CI/CD recommended" in reason


def test_should_use_cicd_no_pmf():
    """Test decision helper for pre-PMF."""
    should_use, reason = reg_test.should_use_cicd(
        deploys_per_month=50,
        team_size=5,
        budget_per_month=300,
        has_pmf=False
    )
    assert should_use is False
    assert "Pre-PMF" in reason


# ============================================================================
# COST ESTIMATOR TESTS
# ============================================================================

def test_estimate_cicd_costs():
    """Test cost estimation returns expected structure."""
    costs = reg_test.estimate_cicd_costs(
        deploys_per_month=50,
        team_size=5
    )

    assert 'github_actions' in costs
    assert 'storage' in costs
    assert 'api_testing' in costs
    assert 'total' in costs

    # All costs should be non-negative
    assert costs['github_actions'] >= 0
    assert costs['storage'] >= 0
    assert costs['api_testing'] >= 0
    assert costs['total'] >= 0

    # Total should be sum of components
    expected_total = (costs['github_actions'] +
                      costs['storage'] +
                      costs['api_testing'])
    assert abs(costs['total'] - expected_total) < 0.01


def test_estimate_cicd_costs_scaling():
    """Test that costs scale with deployment frequency."""
    costs_small = reg_test.estimate_cicd_costs(10, 3)
    costs_large = reg_test.estimate_cicd_costs(100, 10)

    # Larger scale should cost more
    assert costs_large['total'] > costs_small['total']


# ============================================================================
# TEST DATA TESTS
# ============================================================================

def test_example_data_exists():
    """Test that example data file exists and is valid JSON."""
    # Try both old and new paths for backwards compatibility
    data_file = Path("data/example_data.json")
    if not data_file.exists():
        data_file = Path("test_data/example_data.json")

    if data_file.exists():
        with open(data_file, 'r') as f:
            data = json.load(f)

        assert 'test_questions' in data
        assert isinstance(data['test_questions'], list)
        assert len(data['test_questions']) > 0

        # Check first question structure
        first_q = data['test_questions'][0]
        assert 'question' in first_q
        assert 'expected_answer' in first_q
        assert 'contexts' in first_q
    else:
        pytest.skip("Example data file not found (optional for CI)")


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    """Run smoke tests locally."""
    pytest.main([__file__, "-v", "--tb=short"])
