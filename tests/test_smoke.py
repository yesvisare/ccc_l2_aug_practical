"""
Smoke tests for M5.2: Data Pipelines & Orchestration.
Tests basic functionality without requiring external services.
"""
import os
import pytest
import tempfile
import json
from pathlib import Path

# Import functions to test
from m5_2_data_pipelines.core import (
    calculate_file_checksum,
    detect_changed_documents,
    chunk_document,
    embed_chunks,
    process_document_batch,
    upsert_to_pinecone,
    handle_deletions,
    run_incremental_refresh_pipeline
)

from m5_2_data_pipelines.config import validate_config, get_clients


class TestConfiguration:
    """Test configuration loading and validation."""

    def test_config_loads(self):
        """Test that config module loads without errors."""
        from m5_2_data_pipelines.config import DATA_DIR, CHECKSUM_FILE, BATCH_SIZE
        assert DATA_DIR is not None
        assert CHECKSUM_FILE is not None
        assert BATCH_SIZE > 0

    def test_validate_config_returns_bool(self):
        """Test that validate_config returns a boolean."""
        result = validate_config()
        assert isinstance(result, bool)

    def test_get_clients_returns_dict(self):
        """Test that get_clients returns a dictionary."""
        clients = get_clients()
        assert isinstance(clients, dict)
        assert 'openai' in clients
        assert 'pinecone' in clients


class TestChecksumCalculation:
    """Test file checksum calculation."""

    def test_calculate_checksum_basic(self):
        """Test checksum calculation for a simple file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content")
            temp_path = f.name

        try:
            checksum = calculate_file_checksum(temp_path)
            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA256 produces 64-char hex string
        finally:
            os.unlink(temp_path)

    def test_calculate_checksum_consistency(self):
        """Test that same content produces same checksum."""
        content = "Consistent content"

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            temp_path = f.name

        try:
            checksum1 = calculate_file_checksum(temp_path)
            checksum2 = calculate_file_checksum(temp_path)
            assert checksum1 == checksum2
        finally:
            os.unlink(temp_path)

    def test_calculate_checksum_file_not_found(self):
        """Test that missing file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            calculate_file_checksum("/nonexistent/file.txt")


class TestChangeDetection:
    """Test document change detection."""

    def test_detect_changes_new_files(self):
        """Test detecting new files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("New file content")

            checksums_file = os.path.join(tmpdir, "checksums.json")

            # First run - all files are new
            result = detect_changed_documents(tmpdir, checksums_file)

            assert 'changed_files' in result
            assert 'deleted_files' in result
            assert 'current_checksums' in result
            assert len(result['changed_files']) == 1
            assert test_file in result['changed_files']

    def test_detect_changes_no_changes(self):
        """Test that unchanged files are not detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("Unchanged content")

            checksums_file = os.path.join(tmpdir, "checksums.json")

            # First run
            detect_changed_documents(tmpdir, checksums_file)

            # Second run - no changes
            result = detect_changed_documents(tmpdir, checksums_file)

            assert len(result['changed_files']) == 0
            assert len(result['deleted_files']) == 0

    def test_detect_changes_modified_files(self):
        """Test detecting modified files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            checksums_file = os.path.join(tmpdir, "checksums.json")

            # Create and detect initial file
            with open(test_file, 'w') as f:
                f.write("Original content")
            detect_changed_documents(tmpdir, checksums_file)

            # Modify file
            with open(test_file, 'w') as f:
                f.write("Modified content")

            # Detect changes
            result = detect_changed_documents(tmpdir, checksums_file)

            assert len(result['changed_files']) == 1
            assert test_file in result['changed_files']

    def test_detect_changes_deleted_files(self):
        """Test detecting deleted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            checksums_file = os.path.join(tmpdir, "checksums.json")

            # Create and detect initial file
            with open(test_file, 'w') as f:
                f.write("Content")
            detect_changed_documents(tmpdir, checksums_file)

            # Delete file
            os.unlink(test_file)

            # Detect deletion
            result = detect_changed_documents(tmpdir, checksums_file)

            assert len(result['deleted_files']) == 1
            assert test_file in result['deleted_files']


class TestDocumentChunking:
    """Test document chunking functionality."""

    def test_chunk_document_basic(self):
        """Test basic document chunking."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("A" * 1000)  # 1000 characters
            temp_path = f.name

        try:
            chunks = chunk_document(temp_path, chunk_size=512, chunk_overlap=50)

            assert len(chunks) > 0
            assert all('text' in chunk for chunk in chunks)
            assert all('index' in chunk for chunk in chunks)
            assert all('metadata' in chunk for chunk in chunks)
        finally:
            os.unlink(temp_path)

    def test_chunk_document_empty_file(self):
        """Test chunking an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("")
            temp_path = f.name

        try:
            chunks = chunk_document(temp_path)
            assert len(chunks) == 0
        finally:
            os.unlink(temp_path)


class TestEmbedding:
    """Test embedding functionality."""

    def test_embed_chunks_without_client(self):
        """Test that embedding gracefully handles missing client."""
        chunks = [{'text': 'Test chunk 1'}, {'text': 'Test chunk 2'}]

        # Should return empty list when client is None
        embeddings = embed_chunks(chunks, openai_client=None)

        assert isinstance(embeddings, list)
        assert len(embeddings) == 0

    def test_embed_chunks_empty_list(self):
        """Test embedding with empty chunks list."""
        embeddings = embed_chunks([], openai_client=None)
        assert len(embeddings) == 0


class TestProcessing:
    """Test batch processing functionality."""

    def test_process_batch_without_client(self):
        """Test processing gracefully handles missing client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("Test content for processing")

            # Process without OpenAI client
            result = process_document_batch(
                [test_file],
                openai_client=None
            )

            assert isinstance(result, list)
            assert len(result) == 1
            assert 'file_path' in result[0]
            assert 'chunks' in result[0]
            assert 'embeddings' in result[0]
            assert len(result[0]['embeddings']) == 0  # No embeddings without client


class TestUpsertAndDeletions:
    """Test vector database operations."""

    def test_upsert_without_client(self):
        """Test upsert gracefully handles missing client."""
        processed = [{
            'file_path': '/test/file.txt',
            'chunks': [{'text': 'test'}],
            'embeddings': [[0.1] * 1536]
        }]

        # Should return 0 when client is None
        count = upsert_to_pinecone(processed, pinecone_index=None)
        assert count == 0

    def test_handle_deletions_without_client(self):
        """Test deletions gracefully handle missing client."""
        deleted = ['/test/file1.txt', '/test/file2.txt']

        # Should return 0 when client is None
        count = handle_deletions(deleted, pinecone_index=None)
        assert count == 0


class TestFullPipeline:
    """Test the complete pipeline."""

    def test_pipeline_without_api_keys(self):
        """Test that pipeline runs without API keys (graceful degradation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("Test content for full pipeline")

            checksums_file = os.path.join(tmpdir, "checksums.json")

            # Run pipeline without clients
            result = run_incremental_refresh_pipeline(
                documents_path=tmpdir,
                checksums_file=checksums_file,
                openai_client=None,
                pinecone_index=None,
                max_workers=1
            )

            assert result['status'] == 'success'
            assert 'duration_seconds' in result
            assert result.get('vectors_upserted', 0) == 0  # No vectors without clients

    def test_pipeline_no_changes(self):
        """Test pipeline when no changes detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checksums_file = os.path.join(tmpdir, "checksums.json")

            # Run on empty directory
            result = run_incremental_refresh_pipeline(
                documents_path=tmpdir,
                checksums_file=checksums_file,
                openai_client=None,
                pinecone_index=None
            )

            assert result['status'] == 'success'
            assert result['changes_detected'] == False


class TestAPIEndpoints:
    """Test FastAPI endpoints."""

    def test_app_imports(self):
        """Test that app.py imports without errors."""
        try:
            import app
            assert app.app is not None
        except ImportError as e:
            pytest.skip(f"FastAPI not installed: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
