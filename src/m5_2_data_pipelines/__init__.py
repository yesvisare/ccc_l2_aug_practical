"""
M5.2: Data Pipelines & Orchestration package.

This package provides orchestration tools for automated RAG data refresh pipelines.
"""

from .core import (
    calculate_file_checksum,
    detect_changed_documents,
    chunk_document,
    embed_chunks,
    process_document_batch,
    upsert_to_pinecone,
    handle_deletions,
    run_incremental_refresh_pipeline,
)

from .config import (
    get_openai_client,
    get_pinecone_client,
    get_clients,
    validate_config,
    DATA_DIR,
    CHECKSUM_FILE,
    BATCH_SIZE,
    MAX_WORKERS,
)

__all__ = [
    # Core functions
    'calculate_file_checksum',
    'detect_changed_documents',
    'chunk_document',
    'embed_chunks',
    'process_document_batch',
    'upsert_to_pinecone',
    'handle_deletions',
    'run_incremental_refresh_pipeline',
    # Config functions
    'get_openai_client',
    'get_pinecone_client',
    'get_clients',
    'validate_config',
    # Config constants
    'DATA_DIR',
    'CHECKSUM_FILE',
    'BATCH_SIZE',
    'MAX_WORKERS',
]

__version__ = '1.0.0'
