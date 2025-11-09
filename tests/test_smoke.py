"""
Smoke tests for M5.1 Incremental Indexing.

Tests core functionality without requiring API keys or external services.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

from m5_1_incremental_indexing import (
    ChangeDetector,
    IncrementalIndexer,
    IndexVersionManager,
    simple_chunk_function,
    mock_embedding_function,
    DocumentState,
    ChangeReport
)
from m5_1_incremental_indexing import config


class TestChangeDetector:
    """Test ChangeDetector class."""

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            detector = ChangeDetector()
            checksum = detector.calculate_checksum(temp_path)

            # Verify it's a valid SHA-256 hex string
            assert len(checksum) == 64
            assert all(c in '0123456789abcdef' for c in checksum)

            # Verify consistency
            checksum2 = detector.calculate_checksum(temp_path)
            assert checksum == checksum2
        finally:
            os.unlink(temp_path)

    def test_detect_new_document(self):
        """Test detection of new documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("New document content")

            # Create detector with temporary state file
            state_file = os.path.join(tmpdir, "state.json")
            detector = ChangeDetector(state_file=state_file)

            # Detect changes
            report = detector.detect_changes([test_file])

            assert len(report.new) == 1
            assert test_file in report.new
            assert len(report.modified) == 0
            assert len(report.deleted) == 0

    def test_detect_modified_document(self):
        """Test detection of modified documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            state_file = os.path.join(tmpdir, "state.json")

            # Create initial file
            with open(test_file, 'w') as f:
                f.write("Original content")

            # First detection (new document)
            detector = ChangeDetector(state_file=state_file)
            report1 = detector.detect_changes([test_file])
            assert len(report1.new) == 1

            # Update state
            checksum = detector.calculate_checksum(test_file)
            detector.update_state(test_file, checksum, ["chunk1", "chunk2"])
            detector.save()

            # Modify file
            with open(test_file, 'w') as f:
                f.write("Modified content")

            # Reload detector and detect changes
            detector2 = ChangeDetector(state_file=state_file)
            report2 = detector2.detect_changes([test_file])

            assert len(report2.modified) == 1
            assert test_file in report2.modified

    def test_detect_deleted_document(self):
        """Test detection of deleted documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            state_file = os.path.join(tmpdir, "state.json")

            # Create and track file
            with open(test_file, 'w') as f:
                f.write("Content")

            detector = ChangeDetector(state_file=state_file)
            checksum = detector.calculate_checksum(test_file)
            detector.update_state(test_file, checksum, ["chunk1"])
            detector.save()

            # Reload and detect without the file
            detector2 = ChangeDetector(state_file=state_file)
            report = detector2.detect_changes([])

            assert len(report.deleted) == 1
            assert test_file in report.deleted

    def test_state_persistence(self):
        """Test state save and load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")

            # Create detector and add state
            detector1 = ChangeDetector(state_file=state_file)
            detector1.update_state("test.txt", "abc123", ["chunk1", "chunk2"])
            detector1.save()

            # Load in new detector instance
            detector2 = ChangeDetector(state_file=state_file)
            assert "test.txt" in detector2.state
            assert detector2.state["test.txt"].checksum == "abc123"
            assert detector2.state["test.txt"].chunk_ids == ["chunk1", "chunk2"]


class TestIndexVersionManager:
    """Test IndexVersionManager class."""

    def test_create_snapshot(self):
        """Test snapshot creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            versions_dir = os.path.join(tmpdir, "versions")

            # Create state file
            with open(state_file, 'w') as f:
                f.write('{"test": "data"}')

            # Create snapshot
            manager = IndexVersionManager(versions_dir=versions_dir)
            snapshot_id = manager.create_snapshot(state_file)

            assert snapshot_id is not None
            assert len(snapshot_id) > 0

            # Verify snapshot exists
            snapshots = manager.list_snapshots()
            assert snapshot_id in snapshots

    def test_list_snapshots(self):
        """Test listing snapshots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            versions_dir = os.path.join(tmpdir, "versions")

            with open(state_file, 'w') as f:
                f.write('{}')

            manager = IndexVersionManager(versions_dir=versions_dir)

            # Create multiple snapshots
            snapshot1 = manager.create_snapshot(state_file)
            snapshot2 = manager.create_snapshot(state_file)

            snapshots = manager.list_snapshots()
            assert len(snapshots) >= 2
            assert snapshot1 in snapshots
            assert snapshot2 in snapshots

    def test_rollback(self):
        """Test rollback to snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            versions_dir = os.path.join(tmpdir, "versions")

            # Create initial state
            with open(state_file, 'w') as f:
                f.write('{"version": "v1"}')

            manager = IndexVersionManager(versions_dir=versions_dir)
            snapshot_id = manager.create_snapshot(state_file)

            # Modify state
            with open(state_file, 'w') as f:
                f.write('{"version": "v2"}')

            # Rollback
            manager.rollback_to_snapshot(snapshot_id, state_file)

            # Verify rollback
            with open(state_file, 'r') as f:
                content = f.read()
                assert '"version": "v1"' in content


class TestUtilityFunctions:
    """Test utility functions."""

    def test_simple_chunk_function(self):
        """Test text chunking."""
        text = "A" * 1000
        chunks = simple_chunk_function(text, chunk_size=100, overlap=10)

        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)

    def test_mock_embedding_function(self):
        """Test mock embedding generation."""
        text = "Test document content"
        embedding = mock_embedding_function(text)

        # Verify shape
        assert len(embedding) == 384
        assert all(isinstance(v, float) for v in embedding)

        # Verify deterministic
        embedding2 = mock_embedding_function(text)
        assert embedding == embedding2

        # Verify different for different text
        embedding3 = mock_embedding_function("Different text")
        assert embedding != embedding3


class TestConfiguration:
    """Test configuration loading."""

    def test_config_loads(self):
        """Test that config module loads without errors."""
        assert hasattr(config, 'DEFAULT_STATE_FILE')
        assert hasattr(config, 'DEFAULT_BATCH_SIZE')
        assert hasattr(config, 'DEFAULT_CHUNK_SIZE')

    def test_config_defaults(self):
        """Test default configuration values."""
        assert config.DEFAULT_BATCH_SIZE > 0
        assert config.DEFAULT_CHUNK_SIZE > 0
        assert config.DEFAULT_MAX_VERSIONS > 0

    def test_get_clients_without_keys(self):
        """Test client initialization without API keys."""
        # This should not raise, just return mock functions
        clients = config.get_clients()
        assert 'embed_fn' in clients
        assert callable(clients['embed_fn'])


class TestMockIndexer:
    """Test IncrementalIndexer with mock index."""

    def test_process_document(self):
        """Test document processing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test document
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("This is test content for chunking and embedding.")

            # Create mock index
            class MockIndex:
                def delete(self, ids):
                    pass

                def upsert(self, vectors):
                    pass

            state_file = os.path.join(tmpdir, "state.json")
            detector = ChangeDetector(state_file=state_file)

            indexer = IncrementalIndexer(
                index_client=MockIndex(),
                change_detector=detector,
                embedding_function=mock_embedding_function,
                chunk_function=simple_chunk_function,
                batch_size=10
            )

            # Process document
            vectors = indexer.process_document(test_file)

            assert len(vectors) > 0
            for chunk_id, embedding, metadata in vectors:
                assert isinstance(chunk_id, str)
                assert len(embedding) == 384
                assert "source" in metadata
                assert metadata["source"] == test_file


if __name__ == "__main__":
    """Run smoke tests."""
    print("Running M5.1 Incremental Indexing smoke tests...\n")

    # Run with pytest if available
    try:
        pytest.main([__file__, "-v", "--tb=short"])
    except ImportError:
        print("pytest not installed, running manual tests...\n")

        # Manual test execution
        test_classes = [
            TestChangeDetector,
            TestIndexVersionManager,
            TestUtilityFunctions,
            TestConfiguration,
            TestMockIndexer
        ]

        total_tests = 0
        passed_tests = 0

        for test_class in test_classes:
            print(f"\n{test_class.__name__}:")
            test_instance = test_class()

            for method_name in dir(test_instance):
                if method_name.startswith("test_"):
                    total_tests += 1
                    try:
                        method = getattr(test_instance, method_name)
                        method()
                        print(f"  ✓ {method_name}")
                        passed_tests += 1
                    except Exception as e:
                        print(f"  ✗ {method_name}: {e}")

        print(f"\n{'='*60}")
        print(f"Results: {passed_tests}/{total_tests} tests passed")
        print(f"{'='*60}")

        if passed_tests == total_tests:
            print("✅ All smoke tests passed!")
            sys.exit(0)
        else:
            print("❌ Some tests failed")
            sys.exit(1)
