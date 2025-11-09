# M5.1: Incremental Indexing & Updates

> **Module 5: Production Data Management** - Efficient vector database updates without full re-indexing

## Purpose

This lesson teaches you how to avoid re-indexing entire document corpora when only a few documents change. Instead of re-processing 10,000 documents when one is modified, you'll implement SHA-256 checksum-based change detection and update only changed chunks in your vector database. You'll achieve 99.75% time savings and 99.8% cost reduction compared to full re-indexing.

## Concepts Covered

- **Checksum-based change detection**: SHA-256 hashing to identify new, modified, deleted, and unchanged documents
- **Chunk diffing**: Comparing document chunks to detect granular changes
- **Targeted upserts**: Updating only modified vectors in Pinecone/vector databases
- **Deletion handling**: Safely removing old vectors without orphaning data
- **Version snapshots**: Creating rollback points before risky updates
- **Rollback mechanisms**: Recovering from failed updates using saved state

## After Completing This Module

You will be able to:
- Run change detection on document corpora to identify what needs updating
- Update vector indexes incrementally, saving time and cost
- Rollback safely when updates fail using version snapshots
- Operate offline in demo mode without API keys (change detection works locally)
- Make informed decisions about when incremental indexing is appropriate vs. full re-indexing

## Context in Track

This is **Level 2, Module 5.1: Incremental Indexing & Updates** in the Production Data Management track. You're learning how to manage evolving data in production RAG systems. This module feeds directly into M5.2 (Batch Processing Optimization) where you'll handle larger-scale updates, and later into the A/B Testing modules (M8.2) where you'll evaluate incremental vs. full indexing strategies with real metrics.

---

## Overview

This module implements incremental indexing for vector databases, avoiding costly full re-indexing when only small portions of your document corpus change. Instead of re-processing 10,000 documents when one changes, the system detects and updates only modified content.

**Performance**: 99.75% time reduction (3-5s vs 20+ minutes)
**Cost**: 99.8% cost reduction ($0.10 vs $50 per update)
**Best for**: 500-50,000 document corpora with <5 updates/hour

## Quickstart

### 1. Installation

```bash
# Clone repository
git clone <repo-url>
cd ccc_l2_aug_practical

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configuration

Edit `.env` with your credentials:
```env
PINECONE_API_KEY=your_key_here
PINECONE_ENVIRONMENT=your_env_here
OPENAI_API_KEY=your_key_here
```

### 3. Run Tests

**Windows (PowerShell):**
```powershell
powershell -c "$env:PYTHONPATH='$PWD/src'; pytest tests/ -q"
```

**Unix/Linux/Mac:**
```bash
PYTHONPATH="$PWD/src:$PYTHONPATH" pytest tests/ -q
```

Expected output: All tests passed ✓

### 4. Try the Examples

**Option A: Python Script**

Windows (PowerShell):
```powershell
.\scripts\detect.ps1 example_documents
```

Unix/Linux/Mac:
```bash
./scripts/detect.sh example_documents
```

Expected output:
```
📊 Change Detection Report:
  New: 3
  Modified: 0
  Deleted: 0
```

**Option B: Jupyter Notebook**
```bash
jupyter notebook notebooks/L2_M5_1_Incremental_Indexing.ipynb
```

**Option C: REST API**

Windows (PowerShell):
```powershell
.\scripts\run_api.ps1
# Or manually:
powershell -c "$env:PYTHONPATH='$PWD/src'; uvicorn app:app --reload"
```

Unix/Linux/Mac:
```bash
./scripts/run_api.sh
# Or manually:
PYTHONPATH="$PWD/src:$PYTHONPATH" uvicorn app:app --reload
```

Test endpoints in another terminal:
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/detect-changes \
  -H "Content-Type: application/json" \
  -d '{"documents_glob": "example_documents/**/*.txt"}'
```

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  Document Corpus                                     │
│  ┌─────┐ ┌─────┐ ┌─────┐                           │
│  │ Doc1│ │ Doc2│ │ Doc3│                           │
│  └──┬──┘ └──┬──┘ └──┬──┘                           │
│     │       │       │                               │
└─────┼───────┼───────┼───────────────────────────────┘
      │       │       │
      v       v       v
┌─────────────────────────────────────────────────────┐
│  1. Change Detection (SHA-256 Checksums)            │
│     ┌───────────────────────────────────────┐      │
│     │ Compare current checksums with state  │      │
│     │ → New: 1 doc                          │      │
│     │ → Modified: 1 doc                     │      │
│     │ → Deleted: 1 doc                      │      │
│     │ → Unchanged: skip processing          │      │
│     └───────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────┐
│  2. Version Snapshot (Optional)                     │
│     Create backup before updates for rollback       │
│     snapshot_20250107_143022.json                   │
└─────────────────────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────┐
│  3. Delete Old Vectors                              │
│     Remove existing chunks for modified/deleted docs│
│     Prevents orphaned vectors                       │
└─────────────────────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────┐
│  4. Process & Insert New Vectors                    │
│     Chunk → Embed → Upsert (batched)               │
│     Only for new & modified documents               │
└─────────────────────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────┐
│  5. Update State                                    │
│     Save new checksums & chunk IDs to state file    │
│     Atomic write with file locking                  │
└─────────────────────────────────────────────────────┘
```

## Key Components

### ChangeDetector
- **Purpose**: Detects document changes using SHA-256 checksums
- **Features**: Chunked file reading, state persistence, atomic writes
- **Output**: ChangeReport with new/modified/deleted/unchanged lists

### IncrementalIndexer
- **Purpose**: Updates vector index with only changed documents
- **Strategy**: Delete-then-insert pattern prevents orphaned vectors
- **Integration**: Works with Level 1 DocumentPipeline

### IndexVersionManager
- **Purpose**: Creates snapshots for safe rollback
- **Features**: Automatic cleanup, keeps last 10 versions
- **Use case**: Recovery from failed updates

## Common Failures & Fixes

### 1. Orphaned Vectors from Partial Deletions

**Symptom**: Old chunks remain in index after document update
**Cause**: Deletion fails but insertion succeeds
**Fix**: Always delete before inserting; track chunk IDs in state

```python
# Correct pattern (delete-then-insert)
old_chunk_ids = detector.get_chunk_ids(file_path)
if old_chunk_ids:
    indexer.delete_vectors(old_chunk_ids)  # Delete first
indexer.upsert_vectors(new_vectors)        # Then insert
```

### 2. Race Conditions in Concurrent Updates

**Symptom**: State file corruption, lost updates
**Cause**: Multiple processes writing state simultaneously
**Fix**: Use file locking (fcntl) or distributed lock service

```python
# File locking implemented in ChangeDetector._save_state()
fcntl.flock(f.fileno(), fcntl.LOCK_EX)
json.dump(data, f)
fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

### 3. Version Conflicts During Rollback

**Symptom**: Rollback restores wrong version or fails
**Cause**: Snapshot ID confusion, concurrent snapshots
**Fix**: Use timestamp-based IDs, list snapshots before rollback

```bash
# List available snapshots first
python l2_m5_1_incremental_indexing.py list-snapshots

# Rollback to specific snapshot
python l2_m5_1_incremental_indexing.py rollback 20250107_143022
```

### 4. False Positive Change Detection

**Symptom**: Unnecessary re-indexing of unchanged files
**Cause**: Timestamp changes without content changes
**Fix**: Use content checksums (SHA-256), not timestamps

```python
# Checksum-based detection (already implemented)
checksum = detector.calculate_checksum(file_path)
if self.state[path].checksum != checksum:
    modified_docs.append(path)
```

### 5. Partial Failures Leaving Inconsistent State

**Symptom**: Some documents updated, others failed, state unclear
**Cause**: Exception during batch processing
**Fix**: Create snapshot before update, implement retry logic

```python
# Create snapshot before risky operations
snapshot_id = version_manager.create_snapshot(state_file)
try:
    indexer.run_incremental_update(document_paths)
except Exception as e:
    logger.error(f"Update failed: {e}")
    # Rollback if needed
    version_manager.rollback_to_snapshot(snapshot_id, state_file)
```

## Decision Card: When to Use Incremental Indexing

### ✅ Use When:
- Document corpus: **500-50,000 documents**
- Update frequency: **< 5 updates/hour per document**
- Budget constraint: **< $500/month**
- Latency tolerance: **3-5 seconds acceptable**
- No cross-document dependencies

### ❌ Do NOT Use When:
- **Small corpora** (< 500 documents) → Just re-index, it's fast enough
- **High-frequency updates** (> 5/hour) → Use event-driven architecture
- **Cross-document dependencies** → Requires full re-processing
- **Multiple concurrent indexers** → Need distributed locking
- **Sub-second latency required** → Use streaming updates

### Alternatives:

| Scenario | Better Approach | Why |
|----------|----------------|-----|
| < 500 docs | Full re-indexing | Simpler, fast enough |
| > 50K docs | Event-driven ETL | Better scalability |
| Real-time needs | Streaming pipeline | Lower latency |
| High concurrency | Managed service | Built-in coordination |

## Performance Characteristics

| Corpus Size | Change Detection | Update (1 doc) | Full Re-index |
|------------|------------------|----------------|---------------|
| 100 docs   | < 2s            | 3s             | 30s           |
| 1,000 docs | 2-3s            | 3-5s           | 5 min         |
| 10,000 docs| 10-15s          | 3-5s           | 20+ min       |
| 50,000 docs| 60-90s          | 3-5s           | 2+ hours      |

**Cost per update**: ~$0.10 (vs $50 for full re-index)

## Troubleshooting

### Problem: "State file corrupted"
- **Cause**: Interrupted write operation
- **Fix**: Restore from version snapshot
```bash
python l2_m5_1_incremental_indexing.py rollback <snapshot_id>
```

### Problem: "Change detection taking > 30s"
- **Cause**: Too many documents (> 50K)
- **Fix**: Switch to event-driven architecture or database-backed state

### Problem: "Pinecone rate limit errors"
- **Cause**: Batch size too large or too many concurrent requests
- **Fix**: Reduce BATCH_SIZE in .env (try 50 instead of 100)

### Problem: "API returns skipped=true"
- **Cause**: Missing API keys
- **Fix**: Set PINECONE_API_KEY and OPENAI_API_KEY in .env

### Problem: "Vectors not found after update"
- **Cause**: Index not refreshed yet (eventual consistency)
- **Fix**: Wait 1-2 seconds or use index.describe_index_stats()

## Environment Variables

All configuration is managed through environment variables in `.env`:

| Variable | Purpose |
|----------|---------|
| `PINECONE_API_KEY` | Pinecone authentication key for vector database access |
| `PINECONE_ENVIRONMENT` | Pinecone deployment region (e.g., us-west1-gcp) |
| `PINECONE_INDEX_NAME` | Name of the Pinecone index to use (default: incremental-index) |
| `OPENAI_API_KEY` | OpenAI API key for generating text embeddings |
| `OPENAI_MODEL` | Embedding model to use (default: text-embedding-3-small) |
| `STATE_FILE` | Path to JSON file storing document checksums (default: index_state.json) |
| `VERSIONS_DIR` | Directory for version snapshots (default: index_versions) |
| `MAX_VERSIONS` | Number of snapshots to retain (default: 10) |
| `BATCH_SIZE` | Vectors per upsert/delete batch (default: 100) |
| `CHUNK_SIZE` | Characters per document chunk (default: 500) |
| `CHUNK_OVERLAP` | Character overlap between chunks (default: 50) |
| `ENABLE_METRICS` | Enable Prometheus metrics endpoint (default: false) |
| `METRICS_PORT` | Port for metrics server (default: 9090) |

## Mock Mode (Offline Operation)

**The module works without API keys** by automatically falling back to mock mode:

- **Change detection**: ✓ Runs completely offline using local checksums
- **Vector embeddings**: Uses deterministic mock function (no API calls)
- **Vector database**: Uses in-memory mock index (no Pinecone connection)

This enables:
- Learning the concepts without API costs
- Running tests in CI/CD without credentials
- Developing and debugging locally

When API keys are present, the system automatically switches to live mode with real Pinecone and OpenAI services.

## Project Structure

```
ccc_l2_aug_practical/
├── src/
│   └── m5_1_incremental_indexing/   # Core package
│       ├── __init__.py              # Package exports
│       ├── core.py                  # Business logic
│       └── config.py                # Configuration
├── tests/
│   ├── conftest.py                  # Pytest setup
│   └── test_smoke.py                # Smoke tests
├── scripts/
│   ├── run_api.ps1/.sh             # API launcher
│   └── detect.ps1/.sh              # CLI wrapper
├── notebooks/
│   └── L2_M5_1_Incremental_Indexing.ipynb # Tutorial
├── example_documents/               # Sample data
│   ├── doc1_vector_databases.txt
│   ├── doc2_embeddings.txt
│   └── doc3_incremental_indexing.txt
├── app.py                           # FastAPI REST API
├── setup.py                         # Package installer
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment template
├── .gitignore                       # Git exclusions
├── example_data.json                # Dataset metadata
└── README.md                        # This file
```

## API Reference

### REST Endpoints

```bash
# Health check
GET /health

# Detect changes (fast, no updates)
POST /detect-changes
{
  "documents_glob": "example_documents/**/*.txt"
}

# Run incremental update
POST /update-index
{
  "documents_glob": "example_documents/**/*.txt",
  "create_snapshot": true
}

# Query index
POST /query
{
  "query_text": "vector database similarity search",
  "top_k": 5
}

# Version management
POST /snapshot              # Create snapshot
GET  /snapshots             # List snapshots
POST /rollback              # Rollback to snapshot
  {"snapshot_id": "20250107_143022"}
```

### Python API

```python
from l2_m5_1_incremental_indexing import (
    ChangeDetector,
    IncrementalIndexer,
    IndexVersionManager
)

# Detect changes
detector = ChangeDetector(state_file="index_state.json")
report = detector.detect_changes(document_paths)

# Run incremental update
indexer = IncrementalIndexer(
    index_client=pinecone_index,
    change_detector=detector,
    embedding_function=embed_fn,
    chunk_function=chunk_fn
)
stats = indexer.run_incremental_update(document_paths)

# Version management
manager = IndexVersionManager(versions_dir="index_versions")
snapshot_id = manager.create_snapshot("index_state.json")
manager.rollback_to_snapshot(snapshot_id, "index_state.json")
```

## Production Deployment

### Monitoring Metrics

Track these with Prometheus:
- `change_detection_duration_seconds` (P95 target: < 10s)
- `update_success_rate` (target: > 95%)
- `orphaned_vector_count` (should be 0)
- `state_file_size_bytes` (alert at > 100MB)

### Safety Checklist

- [ ] Persistent volume for state file
- [ ] Automated backups of state file
- [ ] Version snapshot before each update
- [ ] File locking enabled (Unix systems)
- [ ] Rate limiting configured
- [ ] Dead letter queue for failed updates
- [ ] Monitoring alerts configured
- [ ] Rollback procedure documented
- [ ] Load testing completed
- [ ] Disaster recovery plan ready

### Environment Variables

See `.env.example` for all configuration options.

## Next Steps

After mastering incremental indexing, explore:

- **M5.2: Batch Processing Optimization** - Efficient bulk updates
- **M5.3: Real-time Streaming Updates** - Event-driven architecture
- **M5.4: Multi-tenant Index Management** - Isolation and access control

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section above
2. Review [Common Failures](#common-failures--fixes)
3. Run smoke tests: `python tests_smoke.py`
4. Open GitHub issue with error logs

---

**Remember**: Incremental indexing is an optimization, not a silver bullet. When in doubt, measure first, then optimize. For small corpora, full re-indexing is often simpler and fast enough.
