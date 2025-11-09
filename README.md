# M5.4: Vector Index Management

**Production Data Management for Pinecone Vector Indexes**

This module provides production-grade tools for managing vector indexes with backup, blue-green deployments, migrations, and cost optimization.

---

## Learning Arc

### **Purpose**

Production-grade vector index management with safe backup/restore workflows, zero-downtime blue-green deployments for model upgrades, verified migrations with sampling checks, and cost-aware operational patterns. Handles S3-backed point-in-time recovery, atomic traffic switching via Redis, namespace-scoped operations, and retention strategies—all designed to operate in demo mode without external services when API keys are absent.

### **Concepts Covered**

- **S3 Backups with Integrity Checks:** Batch export, gzip compression, MD5 checksum validation, metadata storage
- **Zero-Downtime Blue-Green Deployments:** Parallel index provisioning, Redis-coordinated atomic traffic switching, instant rollback
- **Verification During Migrations:** Sampling-based integrity checks (default 100 vectors), transformation hooks, dimension validation
- **Namespace Handling:** Scoped backup/restore operations, multi-tenant isolation patterns
- **Retention Strategy:** Rotation policies (daily/weekly/monthly), automated cleanup, versioned backups
- **Cost Estimation Knobs:** Dual-index costs, storage/query/upsert tracking, budget thresholds
- **Demo-Mode Operation:** Graceful degradation when API keys absent, offline cost calculations, workflow demonstrations without live indexes

### **After Completing**

- Create and verify S3-backed index backups with checksum validation
- Restore indexes to a specific point-in-time from versioned backups
- Execute zero-downtime traffic switches between blue/green index versions
- Run migration dry-runs with transformation functions and sampling verification
- Estimate dual-index costs across storage, queries, upserts, and data transfer
- Operate all workflows in offline demo mode without external API keys

### **Context in Track**

M5.4 completes the **Production Data Management** track (L2), providing operational resilience for vector indexes. It builds on **M5.1 (Incremental Updates)** and **M5.2 (Data Validation)** by adding disaster recovery, zero-downtime deployment patterns, and migration verification. Together with **M5.3 (Monitoring)**, this establishes the foundation for hardened production RAG systems. The module precedes **M6 (Security & Compliance)** and **M7-M8 (Evaluation & Operations)**, where backup/migration strategies integrate with access control, audit logging, and continuous evaluation workflows.

---

## Overview

Managing vector indexes in production requires:
- **Disaster recovery** - Point-in-time backups with integrity verification
- **Zero-downtime deployments** - Blue-green pattern for safe updates
- **Model migrations** - Safe transformations with verification
- **Cost awareness** - Financial tracking and optimization

This module implements all four patterns with realistic trade-offs and failure handling.

---

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required:**
- `PINECONE_API_KEY` - Your Pinecone API key

**Optional (for full functionality):**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - For S3 backups
- `REDIS_HOST`, `REDIS_PORT` - For blue-green coordination

### 3. Verify Configuration

```bash
python config.py
```

Expected output:
```
=== Configuration Check ===
Pinecone API Key: ✓ Set
AWS Credentials: ✓ Set (or ✗ Missing)
Redis Host: localhost:6379
S3 Bucket: vector-index-backups

Validation: ✓ PASSED
```

### 4. Run Smoke Tests

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "$PWD/src"
pytest tests/ -q
```

**Unix/Linux:**
```bash
PYTHONPATH=src pytest tests/ -q
```

### 5. Start API Server

**Windows (PowerShell):**
```powershell
.\scripts\run_api.ps1
# or manually:
$env:PYTHONPATH = "$PWD/src"
uvicorn app:app --reload
```

**Unix/Linux:**
```bash
PYTHONPATH=src uvicorn app:app --reload
```

Visit: http://localhost:8000/docs for interactive API documentation.

### 6. Explore Jupyter Notebook

```bash
jupyter notebook L2_M5_4_Vector_Index_Management.ipynb
```

---

## Environment Variables

All configuration is managed through environment variables (see `.env.example`):

| Variable | Purpose | Required |
|----------|---------|----------|
| `PINECONE_API_KEY` | Pinecone API authentication | No (demo mode works without) |
| `PINECONE_ENVIRONMENT` | Pinecone environment/region (default: us-west1-gcp) | No |
| `AWS_ACCESS_KEY_ID` | AWS authentication for S3 backups | No (backup features disabled without) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 | No |
| `AWS_REGION` | AWS region for S3 bucket (default: us-east-1) | No |
| `S3_BACKUP_BUCKET` | S3 bucket name for index backups | No |
| `REDIS_HOST` | Redis host for blue-green coordination (default: localhost) | No |
| `REDIS_PORT` | Redis port (default: 6379) | No |
| `REDIS_PASSWORD` | Redis password (if required) | No |
| `REDIS_DB` | Redis database number (default: 0) | No |
| `DEFAULT_BATCH_SIZE` | Vectors per batch (default: 1000) | No |
| `DEFAULT_DIMENSION` | Default vector dimension (default: 1536) | No |
| `BACKUP_RETENTION_DAYS` | Days to retain backups (default: 30) | No |

---

## Demo-Mode Operation

**When API keys are missing**, the module operates in demo mode:

- **✓ Cost calculations** work offline (no external calls)
- **✓ Workflow demonstrations** run without live indexes
- **✓ Tests pass** with graceful skips for unavailable services
- **✓ API endpoints** return `{"skipped": true, "reason": "..."}` instead of errors
- **✓ Notebook cells** display skip messages for missing clients

This allows learning and exploration without requiring paid services. Simply add API keys to `.env` when ready for production use.

---

## How It Works

### Architecture Diagram (Text)

```
┌─────────────────────────────────────────────────────────┐
│                   Production System                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ Pinecone     │───▶│ IndexBackup  │───▶ S3 Storage    │
│  │ Vector Index │    │ Manager      │     (Disaster     │
│  └──────────────┘    └──────────────┘      Recovery)    │
│         │                                                 │
│         │            ┌──────────────┐                    │
│         ├───────────▶│ BlueGreen    │───▶ Redis         │
│         │            │ Manager      │     (Coordination) │
│         │            └──────────────┘                    │
│         │                                                 │
│         │            ┌──────────────┐                    │
│         └───────────▶│ Migration    │───▶ Target Index  │
│                      │ Manager      │     (New Model)    │
│                      └──────────────┘                    │
│                                                           │
│                      ┌──────────────┐                    │
│                      │ Cost         │───▶ Analytics      │
│                      │ Calculator   │     Dashboard      │
│                      └──────────────┘                    │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. IndexBackupManager
**Purpose:** Backup and restore Pinecone indexes to S3

**Features:**
- Batch processing (1000 vectors at a time)
- gzip compression (level 6, ~70% reduction)
- MD5 checksum for integrity
- Namespaced backups

**Example:**
```python
from config import get_clients, Config
from l2_m4_vector_index_management import IndexBackupManager

clients = get_clients()
backup_mgr = IndexBackupManager(
    clients['pinecone'],
    clients['s3'],
    Config.S3_BACKUP_BUCKET
)

# Backup
metadata = backup_mgr.backup_index("my-index", namespace="production")
print(f"Backup ID: {metadata.backup_id}")
print(f"Vectors: {metadata.vector_count}")
print(f"Size: {metadata.compressed_size_bytes / (1024**2):.2f} MB")

# Restore
success = backup_mgr.restore_index(
    metadata.s3_key,
    "my-index-restored",
    verify_checksum=True
)
```

#### 2. BlueGreenDeploymentManager
**Purpose:** Zero-downtime index updates

**Workflow:**
1. Create green index with new configuration
2. Populate green while blue serves traffic
3. Atomic traffic switch via Redis flag
4. Monitor green; instant rollback if issues

**Example:**
```python
from l2_m4_vector_index_management import BlueGreenDeploymentManager

bg_mgr = BlueGreenDeploymentManager(clients['pinecone'], clients['redis'])

# Step 1: Create green
bg_mgr.create_green_index(
    "my-index-blue",
    "my-index-green",
    dimension=1536
)

# Step 2: Populate green (your data pipeline)
# ... copy/update vectors ...

# Step 3: Switch traffic
bg_mgr.switch_traffic("my-index-blue", "my-index-green")

# Step 4: Rollback if needed
# bg_mgr.rollback("my-index-blue")
```

#### 3. IndexMigrationManager
**Purpose:** Migrate with optional transformation

**Use cases:**
- Upgrade embedding model (ada-002 → ada-003)
- Change vector dimensions
- Reprocess metadata

**Example:**
```python
from l2_m4_vector_index_management import IndexMigrationManager

migration_mgr = IndexMigrationManager(clients['pinecone'])

# Simple migration (no transformation)
result = migration_mgr.migrate_index(
    "source-index",
    "target-index",
    verify_sample_size=100
)

print(f"Migrated: {result.vectors_migrated}")
print(f"Verified: {result.vectors_verified}")
print(f"Duration: {result.duration_seconds:.2f}s")

# With transformation
def scale_vectors(vector_dict):
    vector_dict['values'] = [v * 0.9 for v in vector_dict['values']]
    return vector_dict

result = migration_mgr.migrate_index(
    "source-index",
    "target-index",
    transform_fn=scale_vectors
)
```

#### 4. CostOptimizationCalculator
**Purpose:** Financial tracking and optimization

**Example:**
```python
from l2_m4_vector_index_management import CostOptimizationCalculator

cost_calc = CostOptimizationCalculator()

# Estimate migration cost
breakdown = cost_calc.estimate_migration_cost(
    vector_count=500_000,
    dimension=1536,
    days_dual_index=7
)

cost_calc.print_cost_breakdown(breakdown)
```

**Output:**
```
=== Cost Breakdown ===
Storage:  $12.34
Queries:  $0.50
Upserts:  $1.00
Transfer: $0.89
─────────────────────────
TOTAL:    $14.73
```

---

## Common Failures & Fixes

### Failure 1: Backup Corruption During Large Transfers (>10GB)

**Symptom:** MD5 checksum mismatch on restore

**Cause:** Network interruptions during S3 upload

**Fix:**
```python
# Implement resumable uploads (S3 multipart)
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=100 * 1024 * 1024,  # 100MB
    max_concurrency=10,
    use_threads=True
)

s3.upload_fileobj(file, bucket, key, Config=config)
```

### Failure 2: Index Switch Timing Issues

**Symptom:** Requests hitting intermediate state during traffic switch

**Cause:** Race condition between Redis flag update and application reads

**Fix:**
```python
# Use atomic flag updates + health check
redis.set('active_index', green_index)  # Atomic
time.sleep(5)  # Wait for connection pool refresh
# Monitor error rates before proceeding
```

### Failure 3: Migration Data Loss from Partial Failures

**Symptom:** Process dies mid-upsert batch

**Cause:** Crash, network timeout, or API rate limit

**Fix:**
```python
# Track batch offsets in persistent storage
redis.set(f'migration:{migration_id}:last_batch', batch_num)

# On restart: resume from last checkpoint
last_batch = int(redis.get(f'migration:{migration_id}:last_batch') or 0)
for i in range(last_batch + 1, total_batches):
    # Continue migration...
```

### Failure 4: Cost Spike from Double Indexing

**Symptom:** Unexpected cloud bill

**Cause:** Forgot to clean up old index after migration

**Fix:**
```python
# Automated cleanup with retention
bg_mgr.cleanup_old_index("my-index-blue")

# Or schedule via cron
# 0 2 * * * python cleanup_old_indexes.py
```

### Failure 5: Rollback Failures (No Working Previous Version)

**Symptom:** Can't rollback because only most recent backup exists

**Cause:** Only keeping one backup

**Fix:**
```python
# Maintain 3+ versioned backups with rotation
# Daily backups: keep latest 7
# Weekly backups: keep latest 4
# Monthly backups: keep latest 12
```

---

## Decision Card

Quick reference for choosing strategies:

| Scenario | Best Approach | Cost | Complexity | Downtime |
|----------|---------------|------|-----------|----------|
| **Simple backup only** | S3 backup/restore | Low | Low | Minutes-Hours |
| **Zero-downtime deployment** | Blue-green | High | High | Zero |
| **Model upgrade** | Blue-green + migration | High | Very High | Zero |
| **Disaster recovery** | Backup rotation | Medium | Medium | Minutes-Hours |
| **Cost-constrained** | Metadata versioning | Low | Low | Minutes |
| **Dev/Staging** | Just reindex | Very Low | Very Low | Hours (acceptable) |

### Decision Tree

```
START
  ├─ Need zero downtime?
  │   ├─ YES → Check budget
  │   │   ├─ >$500/month → Blue-Green
  │   │   └─ <$500/month → Metadata versioning
  │   └─ NO → Check recovery time
  │       ├─ <1 hour needed → Backup/restore
  │       └─ >1 hour OK → Just reindex
  │
  ├─ Model transformation needed?
  │   ├─ YES → Migration with verification
  │   └─ NO → Simple backup/restore
  │
  └─ Index size
      ├─ <10K vectors → Skip blue-green
      ├─ 10K-10M vectors → Blue-green OK
      └─ >10M vectors → Incremental migration
```

---

## Troubleshooting

### Issue: "⚠️ Pinecone client unavailable"

**Cause:** Missing `PINECONE_API_KEY` in `.env`

**Fix:**
1. Get API key from [Pinecone Console](https://app.pinecone.io/)
2. Add to `.env`: `PINECONE_API_KEY=your_key_here`
3. Restart application

### Issue: "⚠️ S3 client unavailable"

**Cause:** Missing AWS credentials

**Fix:**
1. Create IAM user with S3 permissions
2. Add credentials to `.env`:
   ```
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   ```
3. Verify bucket exists: `aws s3 ls s3://vector-index-backups`

### Issue: "⚠️ Redis connection failed"

**Cause:** Redis not running or wrong host/port

**Fix:**
```bash
# Local Redis
docker run -d -p 6379:6379 redis:7

# Or update .env with remote Redis
REDIS_HOST=your-redis-host.com
REDIS_PORT=6379
REDIS_PASSWORD=your_password
```

### Issue: Migration timeouts

**Cause:** Large index size (>10M vectors)

**Fix:**
1. Reduce batch size: `IndexMigrationManager(pc, batch_size=500)`
2. Implement incremental migration with checkpoints
3. Consider Pinecone's native backup/restore (if available)

### Issue: High costs

**Cause:** Running both blue and green indexes for extended period

**Fix:**
1. Set cost alerts: `cost_calc.estimate_migration_cost(...)` before deploying
2. Automate cleanup: `bg_mgr.cleanup_old_index()` after verification
3. Use cheaper index tiers temporarily during migration

---

## API Reference

### REST API Endpoints

**Health Check:**
```bash
GET /health
```

**Backup Operations:**
```bash
POST /backup
{
  "index_name": "my-index",
  "namespace": "production",
  "prefix": "backups"
}

POST /restore
{
  "s3_key": "backups/my-index/backup_id.json.gz",
  "target_index_name": "my-index-restored",
  "verify_checksum": true
}

GET /backups?index_name=my-index
```

**Blue-Green Operations:**
```bash
POST /blue-green/create
{
  "blue_index_name": "my-index-blue",
  "green_index_name": "my-index-green",
  "dimension": 1536
}

POST /blue-green/switch
{
  "blue_index_name": "my-index-blue",
  "green_index_name": "my-index-green"
}

POST /blue-green/rollback?blue_index_name=my-index-blue
```

**Migration:**
```bash
POST /migrate
{
  "source_index_name": "old-index",
  "target_index_name": "new-index",
  "verify_sample_size": 100
}
```

**Cost Estimation:**
```bash
POST /cost/estimate
{
  "vector_count": 500000,
  "dimension": 1536,
  "days_dual_index": 7
}
```

---

## Deployment to Railway

### Steps:

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add M5.4 Vector Index Management"
   git push origin main
   ```

2. **Connect Railway:**
   - Go to [Railway](https://railway.app/)
   - New Project → Deploy from GitHub
   - Select your repository

3. **Set Environment Variables:**
   ```
   PINECONE_API_KEY=...
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   REDIS_HOST=... (Railway Redis add-on)
   S3_BACKUP_BUCKET=...
   ```

4. **Deploy:**
   - Railway auto-deploys `app.py`
   - Visit provided URL + `/docs` for API docs

5. **Schedule Backups (Railway Cron):**
   ```bash
   # Add to railway.json
   {
     "cron": {
       "daily-backup": {
         "schedule": "0 2 * * *",
         "command": "python backup_job.py"
       }
     }
   }
   ```

---

## Next Module

**M6: Security & Compliance**

Topics:
- Access control for vector indexes
- Encryption at rest and in transit
- Audit logging (GDPR, SOC2)
- PII handling in metadata
- Secrets management

---

## Project Structure

```
.
├── l2_m4_vector_index_management.py  # Core module (4 managers)
├── config.py                          # Configuration & client factories
├── app.py                             # FastAPI wrapper
├── requirements.txt                   # Dependencies
├── .env.example                       # Environment template
├── example_data.json                  # Sample vectors
├── L2_M4_Vector_Index_Management.ipynb # Jupyter notebook
├── tests_smoke.py                     # Smoke tests
└── README.md                          # This file
```

---

## Contributing

This module is part of the **CCC L2 Aug Practical** curriculum. For issues or suggestions, please open an issue on the [GitHub repository](https://github.com/yesvisare/ccc_l2_aug_practical).

---

## License

Educational use only. Part of Level 2 Production Data Management curriculum.

---

## Resources

- [Pinecone Documentation](https://docs.pinecone.io/)
- [AWS S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/best-practices.html)
- [Blue-Green Deployment Pattern](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Redis Documentation](https://redis.io/documentation)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Built with honesty about trade-offs, costs, and failure modes.**
