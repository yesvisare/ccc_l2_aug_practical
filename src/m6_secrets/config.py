"""
Configuration module for Secrets Management system.

Loads environment variables and provides typed configuration objects.
Includes validation to prevent production secrets leaks.
"""

import os
from typing import Literal, Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load .env file if it exists (for local development)
load_dotenv()

Environment = Literal["dev", "staging", "prod"]


class VaultConfig:
    """Vault server configuration."""

    def __init__(self):
        self.addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = os.getenv("VAULT_TOKEN")
        self.mount_point = os.getenv("VAULT_MOUNT_POINT", "secret")

        # Validation
        if not self.token:
            logger.warning("⚠️  VAULT_TOKEN not set - will fail if Vault required")

    def is_configured(self) -> bool:
        """Check if Vault is properly configured."""
        return bool(self.token)


class AppConfig:
    """Application configuration with environment validation."""

    def __init__(self):
        # Environment
        self.environment: Environment = os.getenv("ENVIRONMENT", "dev")

        # Validate environment
        if self.environment not in ["dev", "staging", "prod"]:
            raise ValueError(
                f"Invalid ENVIRONMENT: {self.environment}. "
                "Must be dev, staging, or prod"
            )

        # Vault configuration
        self.vault = VaultConfig()

        # Production-specific validation
        if self.environment == "prod":
            if not self.vault.token:
                raise ValueError("VAULT_TOKEN required for production")

            if self.vault.token == "dev-root-token":
                raise ValueError(
                    "SECURITY ERROR: dev-root-token detected in production! "
                    "This should never happen."
                )

        # Feature flags
        self.enable_rotation = os.getenv("ENABLE_ROTATION", "true").lower() == "true"
        self.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        self.fallback_to_env = os.getenv("FALLBACK_TO_ENV", "true").lower() == "true"

        # Rotation settings
        self.rotation_interval_hours = int(os.getenv("ROTATION_INTERVAL_HOURS", "720"))  # 30 days
        self.rotation_grace_period_seconds = int(os.getenv("ROTATION_GRACE_PERIOD", "5"))

        # Cache settings
        self.secret_cache_ttl_seconds = int(os.getenv("SECRET_CACHE_TTL", "300"))  # 5 minutes
        self.secret_cache_maxsize = int(os.getenv("SECRET_CACHE_MAXSIZE", "128"))

        logger.info(f"🚀 Starting in {self.environment.upper()} environment")
        logger.info(f"   Vault: {self.vault.addr}")
        logger.info(f"   Vault configured: {self.vault.is_configured()}")
        logger.info(f"   Fallback to env vars: {self.fallback_to_env}")


def get_clients():
    """
    Get initialized clients for external services.

    Returns:
        Dictionary with initialized clients (if keys available)

    Note: Returns empty dict with warning if Vault not configured.
    """
    config = AppConfig()

    clients = {}

    if not config.vault.is_configured():
        logger.warning("⚠️  Vault not configured - clients not initialized")
        return clients

    try:
        from m6_secrets.core import VaultClient

        # Initialize Vault client
        vault_client = VaultClient(
            vault_addr=config.vault.addr,
            vault_token=config.vault.token,
            environment=config.environment
        )

        clients['vault'] = vault_client

        # Fetch secrets
        try:
            secrets = vault_client.get_rag_secrets()

            # Initialize OpenAI client if key available
            if secrets.get('openai_key'):
                from openai import OpenAI
                clients['openai'] = OpenAI(api_key=secrets['openai_key'])
                logger.info("✅ OpenAI client initialized")

            # Initialize Pinecone if key available
            if secrets.get('pinecone_key'):
                from pinecone import Pinecone
                pc = Pinecone(api_key=secrets['pinecone_key'])
                clients['pinecone'] = pc
                logger.info("✅ Pinecone client initialized")

        except Exception as e:
            logger.error(f"Failed to fetch secrets or initialize clients: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize Vault client: {e}")

    return clients


# Constants
DEFAULT_SECRET_PATH_TEMPLATE = "rag-system/{environment}"
SUPPORTED_ENVIRONMENTS = ["dev", "staging", "prod"]

# Cache configuration
DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes
DEFAULT_CACHE_MAXSIZE = 128

# Rotation configuration
DEFAULT_ROTATION_INTERVAL_HOURS = 720  # 30 days
DEFAULT_ROTATION_GRACE_PERIOD_SECONDS = 5

# Monitoring
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))


if __name__ == "__main__":
    """Test configuration loading."""
    print("=" * 60)
    print("Configuration Test")
    print("=" * 60)

    try:
        config = AppConfig()
        print(f"\n✅ Configuration loaded successfully")
        print(f"Environment: {config.environment}")
        print(f"Vault: {config.vault.addr}")
        print(f"Vault configured: {config.vault.is_configured()}")
        print(f"Enable rotation: {config.enable_rotation}")
        print(f"Fallback to env: {config.fallback_to_env}")

        # Test get_clients
        print("\nTesting get_clients()...")
        clients = get_clients()
        print(f"Initialized clients: {list(clients.keys())}")

    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
