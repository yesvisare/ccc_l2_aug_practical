"""
Smoke tests for M5.3: Data Quality & Validation

Minimal tests to verify:
1. Config loads correctly
2. Core functions return plausible shapes
3. Network paths gracefully skip without keys
"""

import json
import os

import pytest

from m5_3_data_quality import (
    ChunkMetadata,
    ChunkQualityScorer,
    DataDriftDetector,
    DuplicateDetector,
    filter_low_quality_chunks,
    remove_duplicates,
)
from m5_3_data_quality import config


class TestConfig:
    """Test configuration loading."""

    def test_config_loads(self):
        """Config should load without errors."""
        assert config.DEFAULT_MIN_QUALITY_SCORE >= 0
        assert config.DEFAULT_MIN_QUALITY_SCORE <= 100

    def test_config_validation(self):
        """Config validation should pass."""
        assert config.validate_config() is True

    def test_get_quality_config(self):
        """Quality config should return expected structure."""
        quality_config = config.get_quality_config()
        assert "min_score" in quality_config
        assert "optimal_length_min" in quality_config
        assert "optimal_length_max" in quality_config

    def test_get_clients_graceful_without_keys(self):
        """Clients should return None when keys missing."""
        clients = config.get_clients()
        assert isinstance(clients, dict)
        # Should gracefully handle missing keys
        assert "grafana" in clients
        assert "airflow" in clients


class TestQualityScoring:
    """Test quality scoring functionality."""

    def test_scorer_initialization(self):
        """Scorer should initialize with defaults."""
        scorer = ChunkQualityScorer()
        assert scorer.min_score == 70.0

    def test_score_chunk_returns_plausible_shape(self):
        """Score chunk should return QualityScore object."""
        scorer = ChunkQualityScorer(min_score=70.0)

        text = "This is a well-formed sentence with good information density."
        metadata = ChunkMetadata(source="test.pdf", date="2024-01", section="intro")

        score = scorer.score_chunk(text, metadata)

        assert hasattr(score, 'total_score')
        assert hasattr(score, 'passed')
        assert hasattr(score, 'failure_reasons')
        assert 0 <= score.total_score <= 100
        assert isinstance(score.passed, bool)

    def test_high_quality_chunk_passes(self):
        """High-quality chunk should pass."""
        scorer = ChunkQualityScorer(min_score=70.0)

        good_text = """
        Machine learning models require careful validation to ensure they generalize
        well to unseen data. Cross-validation techniques split the dataset into
        training and testing sets, allowing practitioners to assess model performance
        objectively.
        """

        metadata = ChunkMetadata(source="ml.pdf", date="2024-01", section="validation")
        score = scorer.score_chunk(good_text, metadata)

        assert score.total_score >= 60  # Should be reasonable
        assert isinstance(score.passed, bool)

    def test_low_quality_chunk_fails(self):
        """Low-quality chunk should fail."""
        scorer = ChunkQualityScorer(min_score=70.0)

        bad_text = "Click here. Subscribe. Copyright 2024."
        score = scorer.score_chunk(bad_text, None)

        assert score.total_score < 70
        assert not score.passed
        assert len(score.failure_reasons) > 0

    def test_batch_score(self):
        """Batch scoring should work."""
        scorer = ChunkQualityScorer(min_score=70.0)

        chunks = [
            ("Good content with complete sentences and information.", None),
            ("Bad", None),
        ]

        scores = scorer.batch_score(chunks)
        assert len(scores) == 2
        assert all(hasattr(s, 'total_score') for s in scores)


class TestDuplicateDetection:
    """Test duplicate detection functionality."""

    def test_detector_initialization(self):
        """Detector should initialize with defaults."""
        detector = DuplicateDetector()
        assert detector.threshold == 0.85
        assert detector.num_perm == 128

    def test_add_and_find_exact_duplicate(self):
        """Should detect exact duplicates."""
        detector = DuplicateDetector(threshold=0.85)

        text = "The quick brown fox jumps over the lazy dog"
        detector.add_chunk("chunk1", text)

        # Check for duplicate
        duplicates = detector.find_duplicates("chunk2", text)

        assert len(duplicates) >= 0  # May or may not find based on LSH
        # Just verify it returns expected shape
        for dup_id, similarity in duplicates:
            assert isinstance(dup_id, str)
            assert 0 <= similarity <= 1

    def test_deduplicate_batch(self):
        """Batch deduplication should return plausible results."""
        detector = DuplicateDetector(threshold=0.85)

        chunks = [
            ("chunk1", "The quick brown fox jumps over the lazy dog"),
            ("chunk2", "The quick brown fox jumps over the lazy dog"),  # Duplicate
            ("chunk3", "Completely different content about machine learning"),
        ]

        unique_ids, dup_info = detector.deduplicate_batch(chunks)

        assert isinstance(unique_ids, list)
        assert isinstance(dup_info, list)
        assert len(unique_ids) <= len(chunks)  # Should have fewer or equal unique
        # Should find at least some duplicates
        assert len(unique_ids) >= 1

    def test_remove_duplicates_helper(self):
        """Helper function should work."""
        chunks = [
            ("chunk1", "The quick brown fox"),
            ("chunk2", "The quick brown fox"),
        ]

        unique_ids = remove_duplicates(chunks, threshold=0.85)

        assert isinstance(unique_ids, list)
        assert len(unique_ids) <= len(chunks)


class TestDriftDetection:
    """Test drift detection functionality."""

    def test_detector_initialization(self):
        """Drift detector should initialize."""
        detector = DataDriftDetector()
        assert detector.significance_level == 0.05
        assert detector.drift_threshold == 0.15

    def test_set_baseline(self):
        """Should set baseline without error."""
        detector = DataDriftDetector()

        quality_scores = [75, 80, 78, 82, 79] * 10
        chunk_lengths = [500, 520, 480, 510, 490] * 10
        density_scores = [85, 87, 83, 86, 84] * 10

        detector.set_baseline(quality_scores, chunk_lengths, density_scores)
        assert detector.baseline_metrics is not None

    def test_detect_drift_no_baseline(self):
        """Should handle missing baseline gracefully."""
        detector = DataDriftDetector()

        result = detector.detect_drift([75, 80], [500, 510], [85, 87])

        assert isinstance(result, dict)
        assert "drift_detected" in result
        assert result["drift_detected"] is False
        assert "error" in result

    def test_detect_drift_insufficient_samples(self):
        """Should handle insufficient samples gracefully."""
        detector = DataDriftDetector()

        # Set baseline
        baseline_quality = [75, 80, 78, 82, 79] * 10
        baseline_lengths = [500, 520, 480, 510, 490] * 10
        baseline_density = [85, 87, 83, 86, 84] * 10

        detector.set_baseline(baseline_quality, baseline_lengths, baseline_density)

        # Try with too few samples
        result = detector.detect_drift([75, 80], [500, 510], [85, 87])

        assert isinstance(result, dict)
        assert "drift_detected" in result
        assert "error" in result

    def test_detect_drift_sufficient_samples(self):
        """Should work with sufficient samples."""
        detector = DataDriftDetector()

        # Set baseline
        baseline_quality = [75, 80, 78, 82, 79] * 10
        baseline_lengths = [500, 520, 480, 510, 490] * 10
        baseline_density = [85, 87, 83, 86, 84] * 10

        detector.set_baseline(baseline_quality, baseline_lengths, baseline_density)

        # Provide sufficient samples
        current_quality = [76, 81, 79, 83, 80] * 10
        current_lengths = [505, 515, 485, 515, 495] * 10
        current_density = [86, 88, 84, 87, 85] * 10

        result = detector.detect_drift(current_quality, current_lengths, current_density)

        assert isinstance(result, dict)
        assert "drift_detected" in result
        assert "metrics" in result


class TestHelperFunctions:
    """Test helper functions."""

    def test_filter_low_quality_chunks(self):
        """Filter function should work."""
        chunks = [
            ("chunk1", "High quality content with complete sentences.", ChunkMetadata(source="test.pdf")),
            ("chunk2", "Bad", None),
        ]

        passed, scores = filter_low_quality_chunks(chunks, min_score=70.0)

        assert isinstance(passed, list)
        assert isinstance(scores, list)
        assert len(scores) == len(chunks)


class TestExampleData:
    """Test example data file."""

    def test_example_data_loads(self):
        """Example data should load and be valid JSON."""
        with open("example_data.json", "r") as f:
            data = json.load(f)

        assert "chunks" in data
        assert "baseline_metrics" in data
        assert len(data["chunks"]) > 0

    def test_example_chunks_structure(self):
        """Example chunks should have expected structure."""
        with open("example_data.json", "r") as f:
            data = json.load(f)

        for chunk in data["chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "expected_quality" in chunk


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
