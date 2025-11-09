"""
Configuration module for M5.4: Vector Index Management
Reads environment variables and provides SDK client factories.
"""
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Config:
    """Central configuration for vector index management."""

    # Pinecone
    PINECONE_API_KEY: Optional[str] = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: Optional[str] = os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")

    # AWS S3 (for backups)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BACKUP_BUCKET: str = os.getenv("S3_BACKUP_BUCKET", "vector-index-backups")

    # Redis (for blue-green coordination)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Defaults
    DEFAULT_BATCH_SIZE: int = int(os.getenv("DEFAULT_BATCH_SIZE", "1000"))
    DEFAULT_DIMENSION: int = int(os.getenv("DEFAULT_DIMENSION", "1536"))
    DEFAULT_METRIC: str = os.getenv("DEFAULT_METRIC", "cosine")
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    # Cost tracking (Pinecone pricing as of 2024)
    COST_PER_MILLION_QUERIES: float = 0.10
    COST_PER_MILLION_UPSERTS: float = 0.20
    COST_PER_GB_STORAGE_MONTHLY: float = 0.30
    COST_PER_GB_TRANSFER: float = 0.09


def get_pinecone_client():
    """
    Get Pinecone client instance.
    Returns None if API key is missing.
    """
    if not Config.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Client unavailable.")
        return None

    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        logger.info("✓ Pinecone client initialized")
        return pc
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone client: {e}")
        return None


def get_s3_client():
    """
    Get boto3 S3 client instance.
    Returns None if AWS credentials are missing.
    """
    if not Config.AWS_ACCESS_KEY_ID or not Config.AWS_SECRET_ACCESS_KEY:
        logger.warning("⚠️ AWS credentials not found. S3 client unavailable.")
        return None

    try:
        import boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION
        )
        logger.info("✓ S3 client initialized")
        return s3_client
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


def get_redis_client():
    """
    Get Redis client instance.
    Returns None if Redis connection fails.
    """
    try:
        import redis
        redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            password=Config.REDIS_PASSWORD,
            db=Config.REDIS_DB,
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        logger.info("✓ Redis client initialized")
        return redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}. Blue-green coordination unavailable.")
        return None


def get_clients() -> Dict[str, Any]:
    """
    Get all configured clients in a single call.
    Returns dict with 'pinecone', 's3', 'redis' keys (values may be None).
    """
    return {
        'pinecone': get_pinecone_client(),
        's3': get_s3_client(),
        'redis': get_redis_client()
    }


def validate_config() -> bool:
    """
    Validate that minimum required configuration is present.
    Returns True if Pinecone is configured (minimum requirement).
    """
    if not Config.PINECONE_API_KEY:
        logger.error("Missing required: PINECONE_API_KEY")
        return False

    logger.info("✓ Minimum configuration valid (Pinecone API key present)")

    # Warn about optional components
    if not Config.AWS_ACCESS_KEY_ID:
        logger.warning("AWS credentials missing - backup functionality unavailable")
    if not get_redis_client():
        logger.warning("Redis unavailable - blue-green coordination unavailable")

    return True


if __name__ == "__main__":
    print("=== Configuration Check ===")
    print(f"Pinecone API Key: {'✓ Set' if Config.PINECONE_API_KEY else '✗ Missing'}")
    print(f"AWS Credentials: {'✓ Set' if Config.AWS_ACCESS_KEY_ID else '✗ Missing'}")
    print(f"Redis Host: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    print(f"S3 Bucket: {Config.S3_BACKUP_BUCKET}")
    print(f"\nValidation: {'✓ PASSED' if validate_config() else '✗ FAILED'}")
