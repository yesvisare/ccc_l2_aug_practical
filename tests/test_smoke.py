"""
Smoke tests for Module 6.1: PII Detection & Redaction.

Minimal tests to verify:
- Configuration loads correctly
- Core functions return plausible shapes
- Network paths gracefully skip without keys
"""

import pytest

from m6_pii_detection_redaction.config import config, Config
from m6_pii_detection_redaction.core import detect_pii, redact_text
from m6_pii_detection_redaction import (
    PIIDetector,
    RedactionStrategy,
    GDPRDeletionService,
    CustomRecognizerFactory,
    PIIMaskingFilter,
    PRESIDIO_AVAILABLE,
    create_whitelist_patterns,
    load_policy,
    RedactionMode,
)


class TestConfiguration:
    """Test configuration loading."""

    def test_config_loads(self):
        """Verify config loads without errors."""
        assert config is not None
        assert isinstance(config, Config)

    def test_default_values(self):
        """Verify default configuration values."""
        assert 0.0 <= config.PII_CONFIDENCE_THRESHOLD <= 1.0
        assert config.PII_REDACTION_STRATEGY in ["masking", "replacement", "hashing"]
        assert config.MAX_WORKERS > 0

    def test_entity_types_defined(self):
        """Verify default entity types are defined."""
        assert isinstance(config.DEFAULT_ENTITY_TYPES, list)
        assert len(config.DEFAULT_ENTITY_TYPES) > 0
        assert "EMAIL_ADDRESS" in config.DEFAULT_ENTITY_TYPES


class TestPIIMaskingFilter:
    """Test log masking filter."""

    def test_ssn_masking(self):
        """Verify SSN masking in logs."""
        filter_instance = PIIMaskingFilter()
        text = "User SSN is 123-45-6789"
        masked = filter_instance._mask_pii(text)
        assert "123-45-6789" not in masked
        assert "XXX-XX-XXXX" in masked

    def test_email_masking(self):
        """Verify email masking in logs."""
        filter_instance = PIIMaskingFilter()
        text = "Contact john@example.com"
        masked = filter_instance._mask_pii(text)
        assert "john@example.com" not in masked
        assert "<EMAIL_REDACTED>" in masked

    def test_phone_masking(self):
        """Verify phone masking in logs."""
        filter_instance = PIIMaskingFilter()
        text = "Call (555) 123-4567"
        masked = filter_instance._mask_pii(text)
        assert "(555) 123-4567" not in masked
        assert "(XXX) XXX-XXXX" in masked


class TestCustomRecognizers:
    """Test custom recognizer factory."""

    def test_employee_id_recognizer_creation(self):
        """Verify employee ID recognizer can be created."""
        recognizer = CustomRecognizerFactory.create_employee_id_recognizer()

        if PRESIDIO_AVAILABLE:
            assert recognizer is not None
            assert recognizer.supported_entities == ["EMPLOYEE_ID"]
        else:
            assert recognizer is None

    def test_policy_number_recognizer_creation(self):
        """Verify policy number recognizer can be created."""
        recognizer = CustomRecognizerFactory.create_policy_number_recognizer()

        if PRESIDIO_AVAILABLE:
            assert recognizer is not None
            assert recognizer.supported_entities == ["POLICY_NUMBER"]
        else:
            assert recognizer is None


class TestWhitelist:
    """Test whitelist patterns."""

    def test_whitelist_creation(self):
        """Verify whitelist patterns are created."""
        patterns = create_whitelist_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_example_domains_whitelisted(self):
        """Verify common test domains are in whitelist."""
        patterns = create_whitelist_patterns()
        pattern_str = " ".join(patterns)
        assert "example.com" in pattern_str or "@example" in pattern_str


@pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not available")
class TestPIIDetector:
    """Test PII detector functionality (only if Presidio available)."""

    def test_detector_initialization(self):
        """Verify detector initializes correctly."""
        detector = PIIDetector(confidence_threshold=0.5)
        assert detector is not None
        assert detector.confidence_threshold == 0.5

    def test_detect_empty_text_raises_error(self):
        """Verify empty text raises ValueError."""
        detector = PIIDetector(confidence_threshold=0.5)

        with pytest.raises(ValueError):
            detector.detect("")

    def test_detect_returns_list(self):
        """Verify detect returns list of entities."""
        detector = PIIDetector(confidence_threshold=0.5)
        text = "Contact john@example.com"
        entities = detector.detect(text)

        assert isinstance(entities, list)
        # May or may not detect entities depending on threshold/model

    def test_redact_returns_result(self):
        """Verify redact returns PIIDetectionResult."""
        detector = PIIDetector(confidence_threshold=0.5)
        text = "Email: test@example.com"

        result = detector.redact(text, strategy=RedactionStrategy.REPLACEMENT)

        assert result is not None
        assert hasattr(result, 'original_text')
        assert hasattr(result, 'redacted_text')
        assert hasattr(result, 'entities_found')
        assert hasattr(result, 'processing_time_ms')
        assert result.original_text == text

    def test_redact_strategies(self):
        """Verify all redaction strategies work."""
        detector = PIIDetector(confidence_threshold=0.5)
        text = "Test content"

        for strategy in [RedactionStrategy.MASKING, RedactionStrategy.REPLACEMENT, RedactionStrategy.HASHING]:
            result = detector.redact(text, strategy=strategy)
            assert result is not None


@pytest.mark.skipif(PRESIDIO_AVAILABLE, reason="Test for graceful degradation when Presidio unavailable")
class TestGracefulDegradation:
    """Test behavior when Presidio is not available."""

    def test_presidio_unavailable_raises_runtime_error(self):
        """Verify RuntimeError raised when Presidio unavailable."""
        # This test only runs when PRESIDIO_AVAILABLE is False
        with pytest.raises(RuntimeError):
            PIIDetector(confidence_threshold=0.5)


class TestGDPRDeletionService:
    """Test GDPR deletion service."""

    def test_service_initialization(self):
        """Verify service initializes correctly."""
        service = GDPRDeletionService(max_retries=3)
        assert service is not None
        assert service.max_retries == 3

    def test_successful_deletion(self):
        """Verify successful deletion and verification."""
        service = GDPRDeletionService(max_retries=2)

        # Mock callbacks
        deleted = False

        def mock_delete():
            nonlocal deleted
            deleted = True

        def mock_verify():
            return deleted

        success, message = service.delete_and_verify(
            "test-doc-123",
            mock_delete,
            mock_verify
        )

        assert success is True
        assert "verified" in message.lower()

    def test_deletion_failure(self):
        """Verify deletion failure is handled."""
        service = GDPRDeletionService(max_retries=1)

        def mock_delete():
            raise Exception("Delete failed")

        def mock_verify():
            return True

        success, message = service.delete_and_verify(
            "test-doc-456",
            mock_delete,
            mock_verify
        )

        assert success is False
        assert "failed" in message.lower()


class TestSimpleAPI:
    """Test simple convenience API (offline by default)."""

    def test_detect_pii_offline(self):
        """Verify detect_pii handles offline mode gracefully."""
        # Works offline - returns empty list if Presidio unavailable
        result = detect_pii("test text")
        assert isinstance(result, list)

    def test_redact_text_offline(self):
        """Verify redact_text handles offline mode gracefully."""
        # Works offline - returns original text if Presidio unavailable
        result = redact_text("test text")
        assert isinstance(result, dict)
        assert "redacted_text" in result

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not available")
    def test_detect_pii_with_presidio(self):
        """Test detect_pii when Presidio is available."""
        result = detect_pii("Email: test@example.com")
        assert isinstance(result, list)

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not available")
    def test_redact_text_with_presidio(self):
        """Test redact_text when Presidio is available."""
        result = redact_text("Email: test@example.com", mode="replace")
        assert isinstance(result, dict)
        assert "redacted_text" in result
        assert "entities_found" in result

    def test_load_policy_default(self):
        """Test load_policy returns default configuration."""
        policy = load_policy()
        assert isinstance(policy, dict)
        assert "confidence_threshold" in policy
        assert "entity_types" in policy


# Run tests with: pytest tests/test_smoke.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
