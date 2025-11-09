"""
M5.4: Vector Index Management

Production-grade vector index management for Pinecone with backup,
blue-green deployments, migrations, and cost optimization.
"""

from .core import (
    IndexBackupManager,
    BlueGreenDeploymentManager,
    IndexMigrationManager,
    CostOptimizationCalculator,
    BackupMetadata,
    MigrationResult,
    CostBreakdown,
)

from .config import (
    Config,
    get_pinecone_client,
    get_s3_client,
    get_redis_client,
    get_clients,
    validate_config,
)

__all__ = [
    # Core managers
    "IndexBackupManager",
    "BlueGreenDeploymentManager",
    "IndexMigrationManager",
    "CostOptimizationCalculator",
    # Data structures
    "BackupMetadata",
    "MigrationResult",
    "CostBreakdown",
    # Config
    "Config",
    "get_pinecone_client",
    "get_s3_client",
    "get_redis_client",
    "get_clients",
    "validate_config",
]

__version__ = "1.0.0"
