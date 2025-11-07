"""
Configuration management for M5.1 Incremental Indexing.

Loads environment variables and provides client factory functions.
"""

import os
import logging
from typing import Optional, Tuple, Any
from pathlib import Path

# Load environment variables from .env file if present
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_STATE_FILE = os.getenv("STATE_FILE", "index_state.json")
DEFAULT_VERSIONS_DIR = os.getenv("VERSIONS_DIR", "index_versions")
DEFAULT_MAX_VERSIONS = int(os.getenv("MAX_VERSIONS", "10"))
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DEFAULT_CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# Pinecone configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "incremental-index")

# OpenAI configuration (for embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "text-embedding-3-small")

# Monitoring
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "false").lower() == "true"
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))


def get_pinecone_client() -> Optional[Tuple[Any, Any]]:
    """
    Get Pinecone client and index.

    Returns:
        Tuple of (pinecone_instance, index) or None if not configured
    """
    if not PINECONE_API_KEY:
        logger.warning("PINECONE_API_KEY not set, Pinecone client unavailable")
        return None

    try:
        import pinecone

        # Initialize Pinecone
        pinecone.init(
            api_key=PINECONE_API_KEY,
            environment=PINECONE_ENVIRONMENT
        )

        # Get or create index
        if PINECONE_INDEX_NAME not in pinecone.list_indexes():
            logger.info(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")
            pinecone.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=384,  # text-embedding-3-small dimension
                metric="cosine"
            )

        index = pinecone.Index(PINECONE_INDEX_NAME)
        logger.info(f"Connected to Pinecone index: {PINECONE_INDEX_NAME}")
        return pinecone, index

    except ImportError:
        logger.error("pinecone-client not installed. Run: pip install pinecone-client")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone: {e}")
        return None


def get_openai_client():
    """
    Get OpenAI client for embeddings.

    Returns:
        OpenAI client or None if not configured
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, OpenAI client unavailable")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("Connected to OpenAI API")
        return client

    except ImportError:
        logger.error("openai not installed. Run: pip install openai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None


def get_embedding_function(client=None):
    """
    Get embedding function for text.

    Args:
        client: OpenAI client (optional, will create if None)

    Returns:
        Callable that takes text and returns embedding vector
    """
    if client is None:
        client = get_openai_client()

    if client is None:
        # Return mock embedding function
        logger.warning("Using mock embedding function (no OpenAI API key)")
        from l2_m5_1_incremental_indexing import mock_embedding_function
        return mock_embedding_function

    def embed(text: str):
        """Generate embedding using OpenAI API."""
        try:
            response = client.embeddings.create(
                model=OPENAI_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    return embed


def get_clients():
    """
    Get all configured clients.

    Returns:
        Dict with available clients
    """
    clients = {}

    # Pinecone
    pinecone_result = get_pinecone_client()
    if pinecone_result:
        clients['pinecone'], clients['index'] = pinecone_result

    # OpenAI
    openai_client = get_openai_client()
    if openai_client:
        clients['openai'] = openai_client
        clients['embed_fn'] = get_embedding_function(openai_client)
    else:
        # Use mock embedding
        from l2_m5_1_incremental_indexing import mock_embedding_function
        clients['embed_fn'] = mock_embedding_function

    return clients


def validate_configuration() -> bool:
    """
    Validate that required configuration is present.

    Returns:
        True if configuration is valid for production use
    """
    errors = []

    if not PINECONE_API_KEY:
        errors.append("PINECONE_API_KEY not set")

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set (will use mock embeddings)")

    if errors:
        logger.warning("Configuration issues detected:")
        for error in errors:
            logger.warning(f"  - {error}")
        return False

    logger.info("Configuration validated successfully")
    return True


if __name__ == "__main__":
    """Test configuration loading."""
    print("🔧 Configuration Status:")
    print(f"  State File: {DEFAULT_STATE_FILE}")
    print(f"  Versions Dir: {DEFAULT_VERSIONS_DIR}")
    print(f"  Max Versions: {DEFAULT_MAX_VERSIONS}")
    print(f"  Batch Size: {DEFAULT_BATCH_SIZE}")
    print(f"  Chunk Size: {DEFAULT_CHUNK_SIZE}")
    print(f"  Chunk Overlap: {DEFAULT_CHUNK_OVERLAP}")
    print(f"\n🔑 API Keys:")
    print(f"  Pinecone: {'✓ Set' if PINECONE_API_KEY else '✗ Not set'}")
    print(f"  OpenAI: {'✓ Set' if OPENAI_API_KEY else '✗ Not set'}")
    print(f"\n📊 Monitoring:")
    print(f"  Metrics Enabled: {ENABLE_METRICS}")
    print(f"  Metrics Port: {METRICS_PORT}")

    print(f"\n✅ Configuration valid: {validate_configuration()}")
