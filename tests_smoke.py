"""
Smoke tests for Module 7.4: Intelligent Alerting.

Basic tests to verify configuration, core functionality, and graceful degradation.
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from config import Config, get_clients
from l2_m7_intelligent_alerting import (
    AnomalyDetector,
    AlertAggregator,
    PagerDutyIntegration,
    RunbookAutomation,
    Alert,
    Incident,
    load_example_data
)


class TestConfiguration:
    """Test configuration loading."""

    def test_config_loads(self):
        """Test that configuration loads without errors."""
        assert Config.PROMETHEUS_URL is not None
        assert Config.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert Config.ANOMALY_STD_THRESHOLD > 0

    def test_config_validation(self):
        """Test configuration validation."""
        # Should not raise exception
        is_valid = Config.validate()
        assert isinstance(is_valid, bool)

    def test_pagerduty_check(self):
        """Test PagerDuty availability check."""
        has_pd = Config.has_pagerduty()
        assert isinstance(has_pd, bool)


class TestAnomalyDetector:
    """Test anomaly detection functionality."""

    def test_detector_initialization(self):
        """Test that detector initializes with correct parameters."""
        detector = AnomalyDetector(std_threshold=3.0)
        assert detector.std_threshold == 3.0
        assert detector.trained is False

    def test_detector_training(self):
        """Test model training with synthetic data."""
        # Generate synthetic baseline
        baseline_df = pd.DataFrame({
            'ds': pd.date_range(start='2025-11-01', periods=1000, freq='1min'),
            'y': np.random.normal(0.15, 0.02, 1000)
        })

        detector = AnomalyDetector()
        success = detector.train(baseline_df)

        assert success is True
        assert detector.trained is True
        assert detector.model is not None

    def test_detector_insufficient_data(self):
        """Test that detector raises error with insufficient data."""
        baseline_df = pd.DataFrame({
            'ds': pd.date_range(start='2025-11-01', periods=50, freq='1min'),
            'y': np.random.normal(0.15, 0.02, 50)
        })

        detector = AnomalyDetector()

        with pytest.raises(ValueError, match="Insufficient training data"):
            detector.train(baseline_df)

    def test_detector_detection(self):
        """Test anomaly detection on trained model."""
        # Train model
        baseline_df = pd.DataFrame({
            'ds': pd.date_range(start='2025-11-01', periods=1000, freq='1min'),
            'y': np.random.normal(0.15, 0.02, 1000)
        })

        detector = AnomalyDetector()
        detector.train(baseline_df)

        # Test normal value
        result = detector.detect({
            'timestamp': datetime(2025, 11, 7, 10, 0),
            'value': 0.16
        })

        assert result.actual_value == 0.16
        assert result.timestamp == datetime(2025, 11, 7, 10, 0)
        assert result.is_anomaly in [True, False]  # Result depends on model


class TestAlertAggregator:
    """Test alert aggregation."""

    def test_aggregator_initialization(self):
        """Test aggregator initializes correctly."""
        aggregator = AlertAggregator(window_seconds=300)
        assert aggregator.window_seconds == 300
        assert len(aggregator.alert_buffer) == 0

    def test_add_alert(self):
        """Test adding alerts to buffer."""
        aggregator = AlertAggregator()
        alert = Alert(
            id="test_1",
            metric="latency",
            service="api",
            timestamp=datetime.now(),
            severity="high",
            message="High latency"
        )

        aggregator.add_alert(alert)
        assert len(aggregator.alert_buffer) == 1

    def test_aggregate_alerts(self):
        """Test alert aggregation."""
        aggregator = AlertAggregator(window_seconds=300)

        # Add multiple alerts for same service
        base_time = datetime.now()
        for i in range(3):
            alert = Alert(
                id=f"test_{i}",
                metric=f"metric_{i}",
                service="api",
                timestamp=base_time + timedelta(seconds=i*30),
                severity="high",
                message=f"Issue {i}"
            )
            aggregator.add_alert(alert)

        incidents = aggregator.aggregate()

        assert len(incidents) > 0
        assert incidents[0].alert_count == 3
        assert incidents[0].service == "api"


class TestPagerDutyIntegration:
    """Test PagerDuty integration."""

    def test_pagerduty_init_without_credentials(self):
        """Test PagerDuty initializes gracefully without credentials."""
        pd = PagerDutyIntegration(api_key=None, service_id=None)
        assert pd.client is None

    def test_pagerduty_create_incident_skips_gracefully(self):
        """Test incident creation skips without credentials."""
        pd = PagerDutyIntegration(api_key=None, service_id=None)

        incident = Incident(
            id="test_incident",
            service="api",
            timestamp=datetime.now(),
            severity="high",
            alert_count=3,
            alerts=[],
            summary="Test incident"
        )

        result = pd.create_incident(incident)
        assert result is None  # Should skip gracefully


class TestRunbookAutomation:
    """Test runbook automation."""

    def test_runbook_initialization(self):
        """Test runbook automation initializes correctly."""
        automation = RunbookAutomation(enabled=True)
        assert automation.enabled is True
        assert len(automation.runbooks) > 0

    def test_runbook_disabled(self):
        """Test runbook skips when disabled."""
        automation = RunbookAutomation(enabled=False)
        result = automation.execute("cache_full", {"percentage": 20})

        assert result["executed"] is False
        assert result["reason"] == "disabled"

    def test_runbook_unknown_trigger(self):
        """Test runbook handles unknown triggers."""
        automation = RunbookAutomation(enabled=True)
        result = automation.execute("unknown_trigger")

        assert result["executed"] is False
        assert result["reason"] == "unknown_trigger"

    def test_runbook_execution(self):
        """Test runbook executes successfully."""
        automation = RunbookAutomation(enabled=True)
        result = automation.execute("cache_full", {"percentage": 20})

        assert result["executed"] is True
        assert result["trigger"] == "cache_full"
        assert "result" in result


class TestExampleData:
    """Test example data loading."""

    def test_load_example_data(self):
        """Test that example data loads correctly."""
        data = load_example_data()

        assert isinstance(data, dict)
        # If file doesn't exist, returns empty dict (graceful degradation)
        if data:
            assert "anomaly_scenarios" in data or "alert_aggregation_example" in data


class TestGracefulDegradation:
    """Test graceful degradation without external services."""

    def test_clients_without_services(self):
        """Test client initialization handles missing services."""
        clients = get_clients()

        assert isinstance(clients, dict)
        # Should not raise exceptions even if services unavailable


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
