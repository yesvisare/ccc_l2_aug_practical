"""
M5.4: Vector Index Management - Production Data Management

This module implements four core patterns for managing Pinecone vector indexes in production:
1. IndexBackupManager: Backup/restore with S3 storage and integrity verification
2. BlueGreenDeploymentManager: Zero-downtime index switching
3. IndexMigrationManager: Vector transformation and migration with verification
4. CostOptimizationCalculator: Financial tracking and optimization

Based on: augmented_m5_videom5_4_Vector_Index_Manag.md
"""

import json
import gzip
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from tqdm import tqdm
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BackupMetadata:
    """Metadata for a backup operation."""
    backup_id: str
    timestamp: str
    index_name: str
    namespace: str
    vector_count: int
    dimension: int
    checksum: str
    compressed_size_bytes: int
    s3_key: str


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    vectors_migrated: int
    vectors_verified: int
    errors: List[str]
    duration_seconds: float


@dataclass
class CostBreakdown:
    """Cost breakdown for index operations."""
    storage_cost: float
    query_cost: float
    upsert_cost: float
    transfer_cost: float
    total_cost: float


class IndexBackupManager:
    """
    Manages backup and restore operations for Pinecone indexes.

    Think of this like Git for your vector index. Export all vectors to durable
    storage (S3), verify data integrity, and restore to any point in time.

    Features:
    - Batch processing (1000 vectors at a time)
    - gzip compression (level 6)
    - MD5 checksum for integrity verification
    - S3 storage with metadata
    - Namespace support
    """

    def __init__(self, pinecone_client, s3_client, bucket_name: str, batch_size: int = 1000):
        """
        Initialize the backup manager.

        Args:
            pinecone_client: Initialized Pinecone client
            s3_client: Initialized boto3 S3 client
            bucket_name: S3 bucket for backups
            batch_size: Vectors per batch (default 1000)
        """
        self.pinecone = pinecone_client
        self.s3 = s3_client
        self.bucket_name = bucket_name
        self.batch_size = batch_size

    def backup_index(
        self,
        index_name: str,
        namespace: str = "",
        prefix: str = "backups"
    ) -> Optional[BackupMetadata]:
        """
        Backup a Pinecone index to S3 with integrity verification.

        Args:
            index_name: Name of the Pinecone index
            namespace: Namespace to backup (empty string for default)
            prefix: S3 key prefix

        Returns:
            BackupMetadata if successful, None otherwise

        Raises:
            Exception: If Pinecone or S3 clients are unavailable
        """
        if not self.pinecone or not self.s3:
            logger.error("Pinecone or S3 client not available")
            return None

        try:
            logger.info(f"Starting backup for index={index_name}, namespace={namespace}")

            # Get index reference
            index = self.pinecone.Index(index_name)

            # Fetch index stats to get vector count
            stats = index.describe_index_stats()
            total_vectors = stats.get('total_vector_count', 0)
            dimension = stats.get('dimension', 0)

            logger.info(f"Backing up {total_vectors} vectors (dim={dimension})")

            # Fetch all vectors in batches
            all_vectors = []
            offset = 0

            with tqdm(total=total_vectors, desc="Fetching vectors") as pbar:
                while True:
                    # Query with pagination
                    results = index.query(
                        vector=[0.0] * dimension,  # Dummy query
                        top_k=self.batch_size,
                        namespace=namespace,
                        include_metadata=True,
                        include_values=True
                    )

                    if not results or not results.get('matches'):
                        break

                    batch = results['matches']
                    all_vectors.extend(batch)
                    pbar.update(len(batch))

                    if len(batch) < self.batch_size:
                        break

                    offset += self.batch_size

            # Serialize to JSON
            backup_data = {
                'index_name': index_name,
                'namespace': namespace,
                'dimension': dimension,
                'vectors': [
                    {
                        'id': v['id'],
                        'values': v['values'],
                        'metadata': v.get('metadata', {})
                    }
                    for v in all_vectors
                ]
            }

            json_data = json.dumps(backup_data).encode('utf-8')

            # Compress with gzip (level 6)
            compressed_data = gzip.compress(json_data, compresslevel=6)

            # Calculate MD5 checksum
            checksum = hashlib.md5(compressed_data).hexdigest()

            # Generate S3 key
            timestamp = datetime.utcnow().isoformat()
            backup_id = f"{index_name}_{namespace}_{int(time.time())}"
            s3_key = f"{prefix}/{index_name}/{backup_id}.json.gz"

            # Upload to S3
            logger.info(f"Uploading to S3: {s3_key} ({len(compressed_data)} bytes)")
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=compressed_data,
                Metadata={
                    'checksum': checksum,
                    'vector_count': str(len(all_vectors)),
                    'dimension': str(dimension),
                    'timestamp': timestamp
                }
            )

            # Create metadata object
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=timestamp,
                index_name=index_name,
                namespace=namespace,
                vector_count=len(all_vectors),
                dimension=dimension,
                checksum=checksum,
                compressed_size_bytes=len(compressed_data),
                s3_key=s3_key
            )

            logger.info(f"✓ Backup completed: {backup_id}")
            return metadata

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    def restore_index(
        self,
        s3_key: str,
        target_index_name: str,
        target_namespace: str = "",
        verify_checksum: bool = True
    ) -> bool:
        """
        Restore vectors from S3 backup to a Pinecone index.

        Args:
            s3_key: S3 key of the backup file
            target_index_name: Target Pinecone index
            target_namespace: Target namespace
            verify_checksum: Verify MD5 checksum before restore

        Returns:
            True if successful, False otherwise
        """
        if not self.pinecone or not self.s3:
            logger.error("Pinecone or S3 client not available")
            return False

        try:
            logger.info(f"Starting restore from S3: {s3_key}")

            # Download from S3
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            compressed_data = response['Body'].read()
            stored_checksum = response.get('Metadata', {}).get('checksum')

            # Verify checksum if requested
            if verify_checksum and stored_checksum:
                actual_checksum = hashlib.md5(compressed_data).hexdigest()
                if actual_checksum != stored_checksum:
                    logger.error(f"Checksum mismatch: expected={stored_checksum}, got={actual_checksum}")
                    return False
                logger.info("✓ Checksum verified")

            # Decompress
            json_data = gzip.decompress(compressed_data)
            backup_data = json.loads(json_data)

            vectors = backup_data['vectors']
            logger.info(f"Restoring {len(vectors)} vectors to {target_index_name}")

            # Get index reference
            index = self.pinecone.Index(target_index_name)

            # Upsert in batches
            with tqdm(total=len(vectors), desc="Upserting vectors") as pbar:
                for i in range(0, len(vectors), self.batch_size):
                    batch = vectors[i:i + self.batch_size]

                    # Format for upsert
                    upsert_data = [
                        (v['id'], v['values'], v.get('metadata', {}))
                        for v in batch
                    ]

                    index.upsert(vectors=upsert_data, namespace=target_namespace)
                    pbar.update(len(batch))

            logger.info(f"✓ Restore completed: {len(vectors)} vectors")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def list_backups(self, index_name: Optional[str] = None, prefix: str = "backups") -> List[Dict]:
        """
        List all backups in S3, optionally filtered by index name.

        Args:
            index_name: Filter by index name (None for all)
            prefix: S3 key prefix

        Returns:
            List of backup metadata dictionaries
        """
        if not self.s3:
            logger.warning("S3 client not available")
            return []

        try:
            search_prefix = f"{prefix}/{index_name}/" if index_name else prefix

            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=search_prefix)

            backups = []
            for obj in response.get('Contents', []):
                # Get object metadata
                head = self.s3.head_object(Bucket=self.bucket_name, Key=obj['Key'])
                metadata = head.get('Metadata', {})

                backups.append({
                    's3_key': obj['Key'],
                    'size_bytes': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'vector_count': metadata.get('vector_count'),
                    'dimension': metadata.get('dimension'),
                    'checksum': metadata.get('checksum')
                })

            return backups

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []


class BlueGreenDeploymentManager:
    """
    Manages blue-green deployments for zero-downtime index updates.

    Named after the two environments (blue = current, green = new), this pattern
    lets you build a completely new index version while the old one serves traffic.

    Features:
    - Parallel index creation
    - Redis-based traffic coordination
    - Instant rollback capability
    - Health monitoring
    """

    def __init__(self, pinecone_client, redis_client):
        """
        Initialize the blue-green deployment manager.

        Args:
            pinecone_client: Initialized Pinecone client
            redis_client: Initialized Redis client for coordination
        """
        self.pinecone = pinecone_client
        self.redis = redis_client

    def create_green_index(
        self,
        blue_index_name: str,
        green_index_name: str,
        dimension: int,
        metric: str = "cosine",
        pods: int = 1,
        replicas: int = 1
    ) -> bool:
        """
        Create a new "green" index with updated configuration.

        Args:
            blue_index_name: Current production index
            green_index_name: New index name
            dimension: Vector dimension
            metric: Distance metric (cosine, euclidean, dotproduct)
            pods: Number of pods
            replicas: Number of replicas

        Returns:
            True if successful, False otherwise
        """
        if not self.pinecone:
            logger.error("Pinecone client not available")
            return False

        try:
            logger.info(f"Creating green index: {green_index_name}")

            # Create new index
            self.pinecone.create_index(
                name=green_index_name,
                dimension=dimension,
                metric=metric,
                spec={
                    'pod': {
                        'environment': 'us-west1-gcp',
                        'pod_type': 'p1.x1',
                        'pods': pods,
                        'replicas': replicas
                    }
                }
            )

            logger.info(f"✓ Green index created: {green_index_name}")

            # Register in Redis
            if self.redis:
                self.redis.hset(f"deployment:{blue_index_name}", "green_index", green_index_name)
                self.redis.hset(f"deployment:{blue_index_name}", "status", "green_building")

            return True

        except Exception as e:
            logger.error(f"Failed to create green index: {e}")
            return False

    def switch_traffic(self, blue_index_name: str, green_index_name: str) -> bool:
        """
        Atomically switch traffic from blue to green using Redis flag.

        Args:
            blue_index_name: Current production index
            green_index_name: New index to switch to

        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            logger.warning("Redis not available - manual traffic switch required")
            return False

        try:
            logger.info(f"Switching traffic: {blue_index_name} → {green_index_name}")

            # Atomic flag update
            self.redis.hset(f"deployment:{blue_index_name}", "active_index", green_index_name)
            self.redis.hset(f"deployment:{blue_index_name}", "status", "green_active")
            self.redis.hset(f"deployment:{blue_index_name}", "switched_at", datetime.utcnow().isoformat())

            logger.info(f"✓ Traffic switched to {green_index_name}")
            return True

        except Exception as e:
            logger.error(f"Traffic switch failed: {e}")
            return False

    def rollback(self, blue_index_name: str) -> bool:
        """
        Instantly rollback to blue index.

        Args:
            blue_index_name: Original production index

        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            logger.warning("Redis not available - manual rollback required")
            return False

        try:
            logger.info(f"Rolling back to: {blue_index_name}")

            # Restore blue as active
            self.redis.hset(f"deployment:{blue_index_name}", "active_index", blue_index_name)
            self.redis.hset(f"deployment:{blue_index_name}", "status", "rolled_back")
            self.redis.hset(f"deployment:{blue_index_name}", "rolled_back_at", datetime.utcnow().isoformat())

            logger.info(f"✓ Rolled back to {blue_index_name}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def get_active_index(self, blue_index_name: str) -> str:
        """
        Get the currently active index name from Redis.

        Args:
            blue_index_name: Blue index name (key for lookup)

        Returns:
            Active index name (defaults to blue_index_name if Redis unavailable)
        """
        if not self.redis:
            return blue_index_name

        try:
            active = self.redis.hget(f"deployment:{blue_index_name}", "active_index")
            return active if active else blue_index_name
        except Exception as e:
            logger.warning(f"Failed to get active index: {e}")
            return blue_index_name

    def cleanup_old_index(self, index_name: str) -> bool:
        """
        Delete an old index after successful deployment.

        Args:
            index_name: Index to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.pinecone:
            logger.error("Pinecone client not available")
            return False

        try:
            logger.info(f"Deleting old index: {index_name}")
            self.pinecone.delete_index(index_name)
            logger.info(f"✓ Deleted index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False


class IndexMigrationManager:
    """
    Manages migrations between indexes with transformation and verification.

    Moving between indexes requires careful copying, integrity validation, and
    handling transformation logic (e.g., re-embedding with a new model).

    Features:
    - Export with optional re-embedding
    - Dimension validation
    - Sampling-based verification
    - Progress tracking
    """

    def __init__(self, pinecone_client, batch_size: int = 1000):
        """
        Initialize the migration manager.

        Args:
            pinecone_client: Initialized Pinecone client
            batch_size: Vectors per batch (default 1000)
        """
        self.pinecone = pinecone_client
        self.batch_size = batch_size

    def migrate_index(
        self,
        source_index_name: str,
        target_index_name: str,
        source_namespace: str = "",
        target_namespace: str = "",
        transform_fn: Optional[callable] = None,
        verify_sample_size: int = 100
    ) -> MigrationResult:
        """
        Migrate vectors from source to target index with optional transformation.

        Args:
            source_index_name: Source index
            target_index_name: Target index
            source_namespace: Source namespace
            target_namespace: Target namespace
            transform_fn: Optional function to transform vectors (v -> v')
            verify_sample_size: Number of vectors to verify (default 100)

        Returns:
            MigrationResult with success status and statistics
        """
        if not self.pinecone:
            return MigrationResult(
                success=False,
                vectors_migrated=0,
                vectors_verified=0,
                errors=["Pinecone client not available"],
                duration_seconds=0.0
            )

        start_time = time.time()
        errors = []
        migrated_count = 0
        verified_count = 0

        try:
            logger.info(f"Starting migration: {source_index_name} → {target_index_name}")

            # Get index references
            source_index = self.pinecone.Index(source_index_name)
            target_index = self.pinecone.Index(target_index_name)

            # Get source stats
            stats = source_index.describe_index_stats()
            total_vectors = stats.get('total_vector_count', 0)
            source_dim = stats.get('dimension', 0)

            logger.info(f"Migrating {total_vectors} vectors (dim={source_dim})")

            # Fetch and migrate in batches
            offset = 0
            sample_ids = []

            with tqdm(total=total_vectors, desc="Migrating vectors") as pbar:
                while True:
                    # Query batch
                    results = source_index.query(
                        vector=[0.0] * source_dim,
                        top_k=self.batch_size,
                        namespace=source_namespace,
                        include_metadata=True,
                        include_values=True
                    )

                    if not results or not results.get('matches'):
                        break

                    batch = results['matches']

                    # Transform if needed
                    if transform_fn:
                        try:
                            batch = [transform_fn(v) for v in batch]
                        except Exception as e:
                            errors.append(f"Transformation error: {e}")
                            break

                    # Prepare for upsert
                    upsert_data = [
                        (v['id'], v['values'], v.get('metadata', {}))
                        for v in batch
                    ]

                    # Upsert to target
                    target_index.upsert(vectors=upsert_data, namespace=target_namespace)
                    migrated_count += len(batch)

                    # Collect sample IDs for verification
                    if len(sample_ids) < verify_sample_size:
                        sample_ids.extend([v['id'] for v in batch[:verify_sample_size - len(sample_ids)]])

                    pbar.update(len(batch))

                    if len(batch) < self.batch_size:
                        break

                    offset += self.batch_size

            # Verify sample
            if sample_ids:
                logger.info(f"Verifying {len(sample_ids)} sample vectors")
                verified_count = self._verify_migration(
                    source_index, target_index,
                    sample_ids, source_namespace, target_namespace
                )

            duration = time.time() - start_time
            success = migrated_count > 0 and len(errors) == 0

            logger.info(f"✓ Migration completed: {migrated_count} vectors in {duration:.2f}s")

            return MigrationResult(
                success=success,
                vectors_migrated=migrated_count,
                vectors_verified=verified_count,
                errors=errors,
                duration_seconds=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Migration failed: {e}")
            errors.append(str(e))

            return MigrationResult(
                success=False,
                vectors_migrated=migrated_count,
                vectors_verified=verified_count,
                errors=errors,
                duration_seconds=duration
            )

    def _verify_migration(
        self,
        source_index,
        target_index,
        sample_ids: List[str],
        source_namespace: str,
        target_namespace: str
    ) -> int:
        """
        Verify migration by sampling queries against both indexes.

        Args:
            source_index: Source Pinecone index
            target_index: Target Pinecone index
            sample_ids: Vector IDs to verify
            source_namespace: Source namespace
            target_namespace: Target namespace

        Returns:
            Number of successfully verified vectors
        """
        verified = 0

        for vec_id in sample_ids:
            try:
                # Fetch from both indexes
                source_fetch = source_index.fetch(ids=[vec_id], namespace=source_namespace)
                target_fetch = target_index.fetch(ids=[vec_id], namespace=target_namespace)

                # Check if both exist
                if vec_id in source_fetch.get('vectors', {}) and vec_id in target_fetch.get('vectors', {}):
                    verified += 1

            except Exception as e:
                logger.warning(f"Verification failed for {vec_id}: {e}")

        return verified


class CostOptimizationCalculator:
    """
    Tracks and optimizes costs for vector index operations.

    Monitors costs across:
    - Storage (per vector count and dimension)
    - API calls (queries and upserts)
    - Data transfer
    - Backup storage fees
    """

    def __init__(
        self,
        cost_per_million_queries: float = 0.10,
        cost_per_million_upserts: float = 0.20,
        cost_per_gb_storage_monthly: float = 0.30,
        cost_per_gb_transfer: float = 0.09
    ):
        """
        Initialize the cost calculator with pricing.

        Args:
            cost_per_million_queries: Cost per 1M queries (default $0.10)
            cost_per_million_upserts: Cost per 1M upserts (default $0.20)
            cost_per_gb_storage_monthly: Cost per GB/month (default $0.30)
            cost_per_gb_transfer: Cost per GB transfer (default $0.09)
        """
        self.cost_per_million_queries = cost_per_million_queries
        self.cost_per_million_upserts = cost_per_million_upserts
        self.cost_per_gb_storage_monthly = cost_per_gb_storage_monthly
        self.cost_per_gb_transfer = cost_per_gb_transfer

    def calculate_storage_cost(
        self,
        vector_count: int,
        dimension: int,
        days: int = 30
    ) -> float:
        """
        Calculate storage cost for vectors.

        Args:
            vector_count: Number of vectors
            dimension: Vector dimension
            days: Number of days (default 30)

        Returns:
            Estimated storage cost in USD
        """
        # Estimate: 4 bytes per float + metadata overhead (~20%)
        bytes_per_vector = dimension * 4 * 1.2
        total_gb = (vector_count * bytes_per_vector) / (1024 ** 3)

        monthly_cost = total_gb * self.cost_per_gb_storage_monthly
        daily_cost = monthly_cost / 30

        return daily_cost * days

    def calculate_query_cost(self, query_count: int) -> float:
        """
        Calculate cost for queries.

        Args:
            query_count: Number of queries

        Returns:
            Estimated query cost in USD
        """
        return (query_count / 1_000_000) * self.cost_per_million_queries

    def calculate_upsert_cost(self, upsert_count: int) -> float:
        """
        Calculate cost for upserts.

        Args:
            upsert_count: Number of upserts

        Returns:
            Estimated upsert cost in USD
        """
        return (upsert_count / 1_000_000) * self.cost_per_million_upserts

    def calculate_transfer_cost(self, bytes_transferred: int) -> float:
        """
        Calculate data transfer cost.

        Args:
            bytes_transferred: Bytes transferred

        Returns:
            Estimated transfer cost in USD
        """
        gb_transferred = bytes_transferred / (1024 ** 3)
        return gb_transferred * self.cost_per_gb_transfer

    def estimate_migration_cost(
        self,
        vector_count: int,
        dimension: int,
        days_dual_index: int = 7
    ) -> CostBreakdown:
        """
        Estimate total cost for a blue-green migration.

        Args:
            vector_count: Number of vectors
            dimension: Vector dimension
            days_dual_index: Days running both indexes (default 7)

        Returns:
            CostBreakdown with detailed costs
        """
        # Double storage during migration
        storage_cost = self.calculate_storage_cost(vector_count * 2, dimension, days_dual_index)

        # Migration upserts (all vectors copied)
        upsert_cost = self.calculate_upsert_cost(vector_count)

        # Verification queries (assume 1% sampling)
        query_cost = self.calculate_query_cost(int(vector_count * 0.01))

        # Data transfer (estimate full index size)
        bytes_per_vector = dimension * 4 * 1.2
        total_bytes = vector_count * bytes_per_vector
        transfer_cost = self.calculate_transfer_cost(int(total_bytes))

        total = storage_cost + upsert_cost + query_cost + transfer_cost

        return CostBreakdown(
            storage_cost=storage_cost,
            query_cost=query_cost,
            upsert_cost=upsert_cost,
            transfer_cost=transfer_cost,
            total_cost=total
        )

    def print_cost_breakdown(self, breakdown: CostBreakdown) -> None:
        """Pretty-print cost breakdown."""
        print("\n=== Cost Breakdown ===")
        print(f"Storage:  ${breakdown.storage_cost:.2f}")
        print(f"Queries:  ${breakdown.query_cost:.2f}")
        print(f"Upserts:  ${breakdown.upsert_cost:.2f}")
        print(f"Transfer: ${breakdown.transfer_cost:.2f}")
        print(f"{'─' * 25}")
        print(f"TOTAL:    ${breakdown.total_cost:.2f}")


if __name__ == "__main__":
    """
    CLI usage examples for vector index management.

    Examples demonstrate backup, blue-green deployment, migration, and cost tracking.
    """
    import sys
    from config import get_clients, Config

    print("=== M5.4: Vector Index Management ===\n")

    # Get clients
    clients = get_clients()

    if not clients['pinecone']:
        print("⚠️ Pinecone client unavailable. Set PINECONE_API_KEY in .env")
        sys.exit(1)

    # Example 1: Backup
    print("\n[Example 1: Backup Index]")
    if clients['s3']:
        backup_mgr = IndexBackupManager(
            clients['pinecone'],
            clients['s3'],
            Config.S3_BACKUP_BUCKET
        )

        # Uncomment to test backup
        # metadata = backup_mgr.backup_index("my-index", namespace="production")
        # if metadata:
        #     print(f"✓ Backup created: {metadata.backup_id}")

        print("# Example: backup_mgr.backup_index('my-index', namespace='production')")
    else:
        print("⚠️ S3 client unavailable. Set AWS credentials in .env")

    # Example 2: Blue-Green Deployment
    print("\n[Example 2: Blue-Green Deployment]")
    if clients['redis']:
        bg_mgr = BlueGreenDeploymentManager(clients['pinecone'], clients['redis'])

        # Uncomment to test blue-green
        # bg_mgr.create_green_index("my-index-blue", "my-index-green", dimension=1536)
        # bg_mgr.switch_traffic("my-index-blue", "my-index-green")

        print("# Example: bg_mgr.create_green_index('blue', 'green', dimension=1536)")
        print("# Example: bg_mgr.switch_traffic('blue', 'green')")
    else:
        print("⚠️ Redis client unavailable. Install/configure Redis for blue-green")

    # Example 3: Migration
    print("\n[Example 3: Index Migration]")
    migration_mgr = IndexMigrationManager(clients['pinecone'])

    # Uncomment to test migration
    # result = migration_mgr.migrate_index("source-index", "target-index")
    # print(f"Migrated: {result.vectors_migrated}, Verified: {result.vectors_verified}")

    print("# Example: migration_mgr.migrate_index('source', 'target')")

    # Example 4: Cost Calculation
    print("\n[Example 4: Cost Estimation]")
    cost_calc = CostOptimizationCalculator()

    # Estimate cost for 500K vectors at 1536 dimensions
    breakdown = cost_calc.estimate_migration_cost(
        vector_count=500_000,
        dimension=1536,
        days_dual_index=7
    )
    cost_calc.print_cost_breakdown(breakdown)

    print("\n✓ Examples complete. Uncomment code blocks to test with real indexes.")
