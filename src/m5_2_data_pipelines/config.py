"""
Configuration management for M5.2: Data Pipelines & Orchestration.
Loads environment variables and provides client initialization.
"""
import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "rag-documents")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Airflow configuration
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", os.path.expanduser("~/airflow"))
AIRFLOW_DAGS_FOLDER = os.getenv("AIRFLOW_DAGS_FOLDER", f"{AIRFLOW_HOME}/dags")
AIRFLOW_DB_URL = os.getenv("AIRFLOW_DB_URL", "sqlite:///airflow.db")

# Pipeline configuration
DATA_DIR = os.getenv("DATA_DIR", "./data/documents")
CHECKSUM_FILE = os.getenv("CHECKSUM_FILE", "./data/checksums.json")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# Retry configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "60"))

# Alerting configuration
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def get_openai_client():
    """
    Initialize and return OpenAI client.

    Returns:
        OpenAI client instance or None if key not available
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found. Client initialization skipped.")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully")
        return client
    except ImportError:
        logger.error("OpenAI library not installed. Run: pip install openai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None


def get_pinecone_client():
    """
    Initialize and return Pinecone client.

    Returns:
        Pinecone index instance or None if key not available
    """
    if not PINECONE_API_KEY:
        logger.warning("Pinecone API key not found. Client initialization skipped.")
        return None

    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        logger.info(f"Pinecone client initialized for index: {PINECONE_INDEX_NAME}")
        return index
    except ImportError:
        logger.error("Pinecone library not installed. Run: pip install pinecone-client")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone client: {e}")
        return None


def get_clients() -> Dict[str, Any]:
    """
    Initialize all external service clients.

    Returns:
        Dictionary with client instances (may contain None values if keys missing)
    """
    return {
        "openai": get_openai_client(),
        "pinecone": get_pinecone_client()
    }


def validate_config() -> bool:
    """
    Validate that required configuration is present.

    Returns:
        True if configuration is valid, False otherwise
    """
    required_vars = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "PINECONE_API_KEY": PINECONE_API_KEY,
    }

    missing = [var for var, value in required_vars.items() if not value]

    if missing:
        logger.warning(f"Missing required environment variables: {', '.join(missing)}")
        logger.info("⚠️ API calls will be skipped. Set variables in .env file.")
        return False

    return True


if __name__ == "__main__":
    # Test configuration
    print("=== Configuration Test ===")
    print(f"Pinecone Index: {PINECONE_INDEX_NAME}")
    print(f"OpenAI Model: {OPENAI_EMBEDDING_MODEL}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"Batch Size: {BATCH_SIZE}")
    print(f"Max Workers: {MAX_WORKERS}")
    print(f"\nConfiguration Valid: {validate_config()}")

    clients = get_clients()
    print(f"\nOpenAI Client: {'✓ Ready' if clients['openai'] else '✗ Not configured'}")
    print(f"Pinecone Client: {'✓ Ready' if clients['pinecone'] else '✗ Not configured'}")
