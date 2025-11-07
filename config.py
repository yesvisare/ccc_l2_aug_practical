"""
Configuration management for M6.4 Compliance & Audit Logging module.
Loads environment variables and provides access to external service clients.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for audit logging system."""

    # Elasticsearch Configuration
    ELASTICSEARCH_HOST: str = os.getenv("ELASTICSEARCH_HOST", "localhost")
    ELASTICSEARCH_PORT: int = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
    ELASTICSEARCH_SCHEME: str = os.getenv("ELASTICSEARCH_SCHEME", "http")
    ELASTICSEARCH_USER: Optional[str] = os.getenv("ELASTICSEARCH_USER")
    ELASTICSEARCH_PASSWORD: Optional[str] = os.getenv("ELASTICSEARCH_PASSWORD")
    ELASTICSEARCH_INDEX_PREFIX: str = os.getenv("ELASTICSEARCH_INDEX_PREFIX", "audit-logs")

    # Audit Logging Configuration
    AUDIT_ENABLE_HASH_CHAIN: bool = os.getenv("AUDIT_ENABLE_HASH_CHAIN", "true").lower() == "true"
    AUDIT_BATCH_SIZE: int = int(os.getenv("AUDIT_BATCH_SIZE", "100"))
    AUDIT_FLUSH_INTERVAL: int = int(os.getenv("AUDIT_FLUSH_INTERVAL", "30"))  # seconds

    # Data Retention Configuration (in days)
    RETENTION_CONFIDENTIAL: int = int(os.getenv("RETENTION_CONFIDENTIAL", "2555"))  # 7 years
    RETENTION_INTERNAL: int = int(os.getenv("RETENTION_INTERNAL", "1095"))  # 3 years
    RETENTION_PUBLIC: int = int(os.getenv("RETENTION_PUBLIC", "365"))  # 1 year
    RETENTION_SECURITY_CRITICAL: int = int(os.getenv("RETENTION_SECURITY_CRITICAL", "3650"))  # 10 years

    # GDPR Configuration
    GDPR_EXPORT_TIMEOUT_DAYS: int = int(os.getenv("GDPR_EXPORT_TIMEOUT_DAYS", "30"))
    GDPR_DELETION_DELAY_DAYS: int = int(os.getenv("GDPR_DELETION_DELAY_DAYS", "7"))

    # Application Configuration
    APP_NAME: str = os.getenv("APP_NAME", "compliance-audit-logger")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


def get_elasticsearch_config() -> Dict[str, Any]:
    """
    Get Elasticsearch connection configuration.

    Returns:
        Dictionary with Elasticsearch connection parameters
    """
    config = {
        "hosts": [f"{Config.ELASTICSEARCH_SCHEME}://{Config.ELASTICSEARCH_HOST}:{Config.ELASTICSEARCH_PORT}"],
    }

    if Config.ELASTICSEARCH_USER and Config.ELASTICSEARCH_PASSWORD:
        config["basic_auth"] = (Config.ELASTICSEARCH_USER, Config.ELASTICSEARCH_PASSWORD)

    return config


def get_elasticsearch_client():
    """
    Create and return an Elasticsearch client instance.

    Returns:
        Elasticsearch client or None if not available
    """
    try:
        from elasticsearch import Elasticsearch

        es_config = get_elasticsearch_config()
        client = Elasticsearch(**es_config)

        # Test connection
        if client.ping():
            return client
        else:
            return None
    except ImportError:
        print("⚠️ elasticsearch package not installed")
        return None
    except Exception as e:
        print(f"⚠️ Failed to connect to Elasticsearch: {e}")
        return None


def is_elasticsearch_available() -> bool:
    """
    Check if Elasticsearch is available and configured.

    Returns:
        True if Elasticsearch is available, False otherwise
    """
    client = get_elasticsearch_client()
    if client:
        try:
            client.close()
        except:
            pass
        return True
    return False


# Export configuration
config = Config()
