"""
Configuration management for M6.3 RBAC module.

Loads environment variables and provides singleton access to RBAC manager.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration constants"""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/rbac_db"
    )

    # Pinecone
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "rbac-docs")

    # Redis (optional caching)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # RBAC settings
    CASBIN_MODEL_PATH: Optional[str] = os.getenv("CASBIN_MODEL_PATH")
    PERMISSION_CACHE_TTL: int = int(os.getenv("PERMISSION_CACHE_TTL", "300"))  # 5 minutes

    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Monitoring
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "false").lower() == "true"
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# Singleton RBAC manager instance
_rbac_manager = None


def get_rbac_manager():
    """
    Get singleton RBAC manager instance.

    Returns:
        RBACManager instance

    Raises:
        RuntimeError: If DATABASE_URL not configured
    """
    global _rbac_manager

    if _rbac_manager is None:
        if not Config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not configured in environment")

        from .core import RBACManager
        _rbac_manager = RBACManager(
            database_url=Config.DATABASE_URL,
            model_path=Config.CASBIN_MODEL_PATH
        )

    return _rbac_manager


def get_pinecone_client():
    """
    Get Pinecone client if credentials available.

    Returns:
        Pinecone client or None if credentials missing
    """
    if not Config.PINECONE_API_KEY:
        return None

    try:
        import pinecone

        pinecone.init(
            api_key=Config.PINECONE_API_KEY,
            environment=Config.PINECONE_ENVIRONMENT
        )

        return pinecone

    except Exception as e:
        print(f"Failed to initialize Pinecone: {e}")
        return None


def get_redis_client():
    """
    Get Redis client if available.

    Returns:
        Redis client or None if connection fails
    """
    try:
        import redis

        client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )

        # Test connection
        client.ping()
        return client

    except Exception:
        # Redis optional - return None if unavailable
        return None


def has_pinecone() -> bool:
    """Check if Pinecone credentials configured"""
    return bool(Config.PINECONE_API_KEY and Config.PINECONE_ENVIRONMENT)


def has_redis() -> bool:
    """Check if Redis is available"""
    return get_redis_client() is not None


if __name__ == "__main__":
    """Configuration diagnostics"""

    print("=" * 60)
    print("Configuration Status")
    print("=" * 60)

    print(f"\nDatabase URL: {'✓ Configured' if Config.DATABASE_URL else '✗ Missing'}")
    print(f"Pinecone: {'✓ Configured' if has_pinecone() else '✗ Missing'}")
    print(f"Redis: {'✓ Available' if has_redis() else '✗ Not available'}")

    print(f"\nAPI Settings:")
    print(f"  Host: {Config.API_HOST}")
    print(f"  Port: {Config.API_PORT}")

    print(f"\nRBAC Settings:")
    print(f"  Model path: {Config.CASBIN_MODEL_PATH or 'Default'}")
    print(f"  Cache TTL: {Config.PERMISSION_CACHE_TTL}s")

    print(f"\nMonitoring:")
    print(f"  Metrics enabled: {Config.ENABLE_METRICS}")
    print(f"  Log level: {Config.LOG_LEVEL}")

    print("\n" + "=" * 60)
