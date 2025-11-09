"""
Module 6.2: Secrets Management & Rotation

Enterprise-grade secrets management using HashiCorp Vault with zero-downtime
key rotation, automated secret scanning, and multi-environment isolation.
"""

from .core import (
    VaultClient,
    ResilientVaultClient,
    SecretRotationManager,
    setup_detect_secrets,
    scan_git_history,
    create_gitignore_for_secrets,
    validate_environment_config,
)

from .config import (
    AppConfig,
    VaultConfig,
    get_clients,
)

__all__ = [
    # Core classes
    "VaultClient",
    "ResilientVaultClient",
    "SecretRotationManager",

    # Utility functions
    "setup_detect_secrets",
    "scan_git_history",
    "create_gitignore_for_secrets",
    "validate_environment_config",

    # Configuration
    "AppConfig",
    "VaultConfig",
    "get_clients",
]

__version__ = "1.0.0"
