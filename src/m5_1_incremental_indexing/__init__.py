"""
M5.1 Incremental Indexing & Updates Package

Re-exports core functionality for clean imports.
"""

from .core import (
    ChangeDetector,
    IncrementalIndexer,
    IndexVersionManager,
    DocumentState,
    ChangeReport,
    simple_chunk_function,
    mock_embedding_function,
)

from .config import (
    get_pinecone_client,
    get_openai_client,
    get_embedding_function,
    get_clients,
    validate_configuration,
    DEFAULT_STATE_FILE,
    DEFAULT_VERSIONS_DIR,
    DEFAULT_MAX_VERSIONS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)

__all__ = [
    # Core classes
    "ChangeDetector",
    "IncrementalIndexer",
    "IndexVersionManager",
    "DocumentState",
    "ChangeReport",
    # Utility functions
    "simple_chunk_function",
    "mock_embedding_function",
    # Config functions
    "get_pinecone_client",
    "get_openai_client",
    "get_embedding_function",
    "get_clients",
    "validate_configuration",
    # Config constants
    "DEFAULT_STATE_FILE",
    "DEFAULT_VERSIONS_DIR",
    "DEFAULT_MAX_VERSIONS",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
]
