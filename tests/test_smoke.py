"""
Smoke tests for M5.4: Vector Index Management

Minimal tests to verify:
- Config loads correctly
- Core functions return plausible shapes
- Network paths gracefully skip without keys
"""

import pytest

from m5_4_vector_index.config import Config, validate_config, get_clients
from m5_4_vector_index.core import (
    IndexBackupManager,
    BlueGreenDeploymentManager,
    IndexMigrationManager,
    CostOptimizationCalculator,
    BackupMetadata,
    MigrationResult,
    CostBreakdown
)


class TestConfig:
    """Test configuration loading."""

    def test_config_constants_exist(self):
        """Verify config constants are defined."""
        assert hasattr(Config, 'DEFAULT_BATCH_SIZE')
        assert hasattr(Config, 'DEFAULT_DIMENSION')
        assert hasattr(Config, 'S3_BACKUP_BUCKET')
        assert hasattr(Config, 'BACKUP_RETENTION_DAYS')

    def test_config_cost_constants(self):
        """Verify cost tracking constants."""
        assert Config.COST_PER_MILLION_QUERIES > 0
        assert Config.COST_PER_MILLION_UPSERTS > 0
        assert Config.COST_PER_GB_STORAGE_MONTHLY > 0

    def test_validate_config_returns_bool(self):
        """Config validation returns boolean."""
        result = validate_config()
        assert isinstance(result, bool)

    def test_get_clients_returns_dict(self):
        """get_clients returns dict with expected keys."""
        clients = get_clients()
        assert isinstance(clients, dict)
        assert 'pinecone' in clients
        assert 's3' in clients
        assert 'redis' in clients


class TestCostOptimizationCalculator:
    """Test cost calculator (no external dependencies)."""

    def setup_method(self):
        """Initialize calculator for each test."""
        self.calc = CostOptimizationCalculator()

    def test_storage_cost_positive(self):
        """Storage cost is positive for non-zero vectors."""
        cost = self.calc.calculate_storage_cost(10000, 1536, 30)
        assert cost > 0

    def test_query_cost_scales(self):
        """Query cost scales with query count."""
        cost_1k = self.calc.calculate_query_cost(1000)
        cost_1m = self.calc.calculate_query_cost(1_000_000)
        assert cost_1m > cost_1k

    def test_upsert_cost_scales(self):
        """Upsert cost scales with upsert count."""
        cost_1k = self.calc.calculate_upsert_cost(1000)
        cost_1m = self.calc.calculate_upsert_cost(1_000_000)
        assert cost_1m > cost_1k

    def test_migration_cost_breakdown_structure(self):
        """Migration cost breakdown has expected structure."""
        breakdown = self.calc.estimate_migration_cost(50000, 1536, 7)

        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.storage_cost >= 0
        assert breakdown.query_cost >= 0
        assert breakdown.upsert_cost >= 0
        assert breakdown.transfer_cost >= 0
        assert breakdown.total_cost >= 0

    def test_total_cost_is_sum(self):
        """Total cost equals sum of components."""
        breakdown = self.calc.estimate_migration_cost(50000, 1536, 7)

        expected_total = (
            breakdown.storage_cost +
            breakdown.query_cost +
            breakdown.upsert_cost +
            breakdown.transfer_cost
        )

        assert abs(breakdown.total_cost - expected_total) < 0.01


class TestBackupManager:
    """Test backup manager initialization (without live connections)."""

    def test_backup_manager_init(self):
        """Backup manager can be initialized with None clients."""
        # Should not crash even with None clients
        manager = IndexBackupManager(None, None, "test-bucket")
        assert manager.bucket_name == "test-bucket"
        assert manager.batch_size == 1000

    def test_backup_fails_gracefully_without_clients(self):
        """Backup returns None when clients unavailable."""
        manager = IndexBackupManager(None, None, "test-bucket")
        result = manager.backup_index("test-index")
        assert result is None

    def test_restore_fails_gracefully_without_clients(self):
        """Restore returns False when clients unavailable."""
        manager = IndexBackupManager(None, None, "test-bucket")
        result = manager.restore_index("test-key", "test-index")
        assert result is False

    def test_list_backups_returns_empty_without_s3(self):
        """List backups returns empty list without S3."""
        manager = IndexBackupManager(None, None, "test-bucket")
        backups = manager.list_backups()
        assert isinstance(backups, list)
        assert len(backups) == 0


class TestBlueGreenManager:
    """Test blue-green manager initialization."""

    def test_bluegreen_manager_init(self):
        """Blue-green manager can be initialized with None clients."""
        manager = BlueGreenDeploymentManager(None, None)
        assert manager.pinecone is None
        assert manager.redis is None

    def test_create_green_fails_without_pinecone(self):
        """Create green returns False without Pinecone."""
        manager = BlueGreenDeploymentManager(None, None)
        result = manager.create_green_index("blue", "green", 1536)
        assert result is False

    def test_switch_traffic_fails_without_redis(self):
        """Switch traffic returns False without Redis."""
        manager = BlueGreenDeploymentManager(None, None)
        result = manager.switch_traffic("blue", "green")
        assert result is False

    def test_get_active_index_defaults_to_blue(self):
        """Get active index defaults to blue without Redis."""
        manager = BlueGreenDeploymentManager(None, None)
        active = manager.get_active_index("my-blue-index")
        assert active == "my-blue-index"


class TestMigrationManager:
    """Test migration manager initialization."""

    def test_migration_manager_init(self):
        """Migration manager can be initialized with None client."""
        manager = IndexMigrationManager(None, batch_size=500)
        assert manager.pinecone is None
        assert manager.batch_size == 500

    def test_migrate_fails_gracefully_without_pinecone(self):
        """Migration returns failure result without Pinecone."""
        manager = IndexMigrationManager(None)
        result = manager.migrate_index("source", "target")

        assert isinstance(result, MigrationResult)
        assert result.success is False
        assert result.vectors_migrated == 0
        assert len(result.errors) > 0


class TestDataClasses:
    """Test dataclass structures."""

    def test_backup_metadata_structure(self):
        """BackupMetadata has expected fields."""
        metadata = BackupMetadata(
            backup_id="test",
            timestamp="2024-01-01T00:00:00Z",
            index_name="test-index",
            namespace="default",
            vector_count=1000,
            dimension=1536,
            checksum="abc123",
            compressed_size_bytes=1024,
            s3_key="backups/test.gz"
        )

        assert metadata.backup_id == "test"
        assert metadata.vector_count == 1000
        assert metadata.dimension == 1536

    def test_migration_result_structure(self):
        """MigrationResult has expected fields."""
        result = MigrationResult(
            success=True,
            vectors_migrated=5000,
            vectors_verified=100,
            errors=[],
            duration_seconds=120.5
        )

        assert result.success is True
        assert result.vectors_migrated == 5000
        assert result.duration_seconds == 120.5

    def test_cost_breakdown_structure(self):
        """CostBreakdown has expected fields."""
        breakdown = CostBreakdown(
            storage_cost=10.0,
            query_cost=1.0,
            upsert_cost=2.0,
            transfer_cost=0.5,
            total_cost=13.5
        )

        assert breakdown.storage_cost == 10.0
        assert breakdown.total_cost == 13.5


def test_imports():
    """Verify all imports work."""
    # If we got here, all imports succeeded
    assert IndexBackupManager is not None
    assert BlueGreenDeploymentManager is not None
    assert IndexMigrationManager is not None
    assert CostOptimizationCalculator is not None


if __name__ == "__main__":
    """Run smoke tests."""
    print("=== Running Smoke Tests for M5.4 ===\n")

    # Run pytest
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    if exit_code == 0:
        print("\n✓ All smoke tests passed!")
    else:
        print("\n✗ Some tests failed")

    sys.exit(exit_code)
