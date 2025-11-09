# Module 5.2: Data Pipelines & Orchestration

**Level:** 2 (Production Data Management)
**Duration:** 38 minutes
**Prerequisites:** Level 1 M1.3 (Document Processing), M5.1 (Incremental Indexing)

---

## Purpose

This module teaches you to orchestrate automated RAG data refresh pipelines using Apache Airflow. You'll learn to schedule updates (daily, hourly, or on-demand), implement parallel processing to reduce refresh time from 40 minutes to 8 minutes for 5,000 documents, handle pipeline failures gracefully with automatic retries, and monitor pipeline health with metrics that pinpoint bottlenecks.

## Concepts Covered

- **Checksum-based change detection** — Identify new, modified, and deleted documents without full re-indexing
- **Batching & parallelism** — Process documents in batches across multiple workers for efficiency
- **Targeted upserts** — Update only changed vectors in Pinecone, preserving unchanged data
- **Deletion handling** — Remove vectors for deleted documents automatically
- **Scheduling options** — Automate with cron jobs, Airflow DAGs, or manual triggers
- **Alerting & retries** — Implement exponential backoff and failure notifications
- **Demo-mode operation** — Run pipeline without API keys for testing and development

## After Completing This Module

You will be able to:
- Run `detect_changed_documents()` to identify files requiring updates
- Execute `run_incremental_refresh_pipeline()` to process changes end-to-end
- Monitor pipeline status via FastAPI endpoints (`/health`, `/status`)
- Operate in offline mode (demo mode) when API keys are unavailable
- Prepare for M5.3 (Data Quality & Validation) where you'll add quality checks to this pipeline

## Context in Track

**M5.2: Data Pipelines & Orchestration** sits within **Level 2: Production Data Management**. It builds directly on **M5.1 (Incremental Indexing)** by automating the manual refresh process. The pipelines you build here feed into **M5.3 (Data Quality & Validation)** for quality checks and **M8 (Evaluation & Testing)** for A/B testing different refresh strategies. This module is critical for production RAG systems that must stay synchronized with evolving document sources.

---

## Overview

This module teaches Apache Airflow orchestration for automated RAG data refresh pipelines. You'll learn how to schedule automated data refreshes, implement parallel processing, handle failures gracefully, and monitor pipeline health.

**Key Learning:**
- Schedule automated pipelines that run daily, hourly, or on-demand
- Implement parallel processing (40 min → 8 min for 5K documents)
- Handle pipeline failures with automatic retries and alerting
- **Critical:** Understand when Airflow is overkill and what simpler alternatives exist

---

## The Problem

In M5.1, you built incremental indexing that detects changed documents and updates only what's necessary. It works beautifully... **when you remember to run it**.

But in production:
- Documents update at 2 AM, but your RAG serves stale data
- Nobody manually triggered the refresh
- Your legal team asks questions about new policies
- Your RAG gives outdated answers
- **Trust in your system takes a hit**

**You need orchestration.**

---

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API keys
# OPENAI_API_KEY=sk-...
# PINECONE_API_KEY=...
```

### 3. Run the Notebook

```bash
jupyter notebook L2_M2_DataPipelines_Orchestration.ipynb
```

### 4. Or Use the API

**Windows (PowerShell):**
```powershell
# Start the FastAPI server
.\scripts\run_api.ps1

# Or manually:
$env:PYTHONPATH = "$PWD/src;$PWD"
uvicorn app:app --reload
```

**Unix/Linux/macOS:**
```bash
# Start the FastAPI server
./scripts/run_api.sh

# Or manually:
export PYTHONPATH="$PWD/src:$PWD"
uvicorn app:app --reload
```

**Test the API:**
```bash
# In another terminal, trigger a refresh
curl -X POST http://localhost:8000/refresh

# Check status
curl http://localhost:8000/status
```

### 5. Run Tests

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "$PWD/src;$PWD"
pytest tests/ -q
```

**Unix/Linux/macOS:**
```bash
export PYTHONPATH="$PWD/src:$PWD"
pytest tests/ -q
```

### 6. Demo Mode (No API Keys)

**The pipeline works without API keys!** If `OPENAI_API_KEY` or `PINECONE_API_KEY` are missing:
- ✅ Change detection runs normally (checksum comparison)
- ✅ Document chunking works locally
- ⚠️ Embedding generation is skipped (prints warning)
- ⚠️ Vector upserts are skipped (prints warning)
- ✅ Pipeline completes successfully with status report

This allows you to test the orchestration logic, scheduling, and monitoring without external dependencies.

---

## How It Works

### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    DAG DEFINITION                   │
│  (Your Python file describing workflow)             │
│                                                      │
│  detect_changes → chunk_documents → embed → upsert  │
│        │                                      ▲      │
│        └──────── (depends on) ────────────────┘     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 EXECUTOR (Celery)                   │
│  (Distributes tasks to workers)                     │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼
    Worker 1   Worker 2   Worker 3   Worker 4
    (Process  (Process   (Process   (Process
     Doc 1-    Doc 501-   Doc 1001-  Doc 1501-
     500)      1000)      1500)      2000)
```

### Pipeline Stages

1. **Detect Changes:** Compare current file checksums with previous checksums
2. **Process Documents:** Chunk and embed changed documents in batches
3. **Upsert to Pinecone:** Update vector database with new embeddings
4. **Handle Deletions:** Remove vectors for deleted documents

### Key Concepts

- **DAG (Directed Acyclic Graph):** Workflow definition with task dependencies
- **Task:** Unit of work (detect changes, embed documents, etc.)
- **Operator:** Template for a task (PythonOperator, BashOperator)
- **Scheduler:** Monitors DAGs and triggers execution when conditions met
- **Executor:** Determines how tasks run (sequential vs. parallel)
- **XCom:** Cross-communication mechanism for passing data between tasks

---

## Environment Variables

Configure the pipeline by setting these variables in `.env` (copy from `.env.example`):

### OpenAI Configuration
- `OPENAI_API_KEY` — API key for generating embeddings (required for production)
- `OPENAI_EMBEDDING_MODEL` — Embedding model to use (default: text-embedding-3-small)

### Pinecone Configuration
- `PINECONE_API_KEY` — API key for vector database access (required for production)
- `PINECONE_ENVIRONMENT` — Pinecone environment region (default: us-west1-gcp)
- `PINECONE_INDEX_NAME` — Name of the vector index (default: rag-documents)

### Airflow Configuration
- `AIRFLOW_HOME` — Airflow installation directory (default: ~/airflow)
- `AIRFLOW_DAGS_FOLDER` — Directory containing DAG definitions (default: ~/airflow/dags)
- `AIRFLOW_DB_URL` — Database connection string for metadata storage

### Pipeline Configuration
- `DATA_DIR` — Directory containing documents to process (default: ./data/documents)
- `CHECKSUM_FILE` — File storing checksums for change detection (default: ./data/checksums.json)
- `BATCH_SIZE` — Number of documents to process per batch (default: 100)
- `MAX_WORKERS` — Number of parallel workers for processing (default: 4)
- `CHUNK_SIZE` — Target size of document chunks in characters (default: 512)
- `CHUNK_OVERLAP` — Overlap between consecutive chunks (default: 50)

### Retry Configuration
- `MAX_RETRIES` — Maximum retry attempts for failed tasks (default: 3)
- `RETRY_DELAY_SECONDS` — Delay between retry attempts (default: 60)

### Alerting Configuration (Optional)
- `ALERT_EMAIL` — Email address for failure notifications
- `SLACK_WEBHOOK_URL` — Slack webhook for pipeline alerts

---

## Common Failures & Fixes

### Failure 1: Pipeline Deadlock

**Symptom:** Tasks hang indefinitely, workers appear stuck

**Cause:** Database connection pool exhaustion

**Fix:**
```python
# Limit connection pool size
from sqlalchemy import create_engine
engine = create_engine(DB_URL, pool_size=10, max_overflow=20)

# Set task timeout
task = PythonOperator(
    task_id='process',
    execution_timeout=timedelta(minutes=30)
)
```

---

### Failure 2: Overlapping Runs

**Symptom:** Multiple pipeline instances running simultaneously

**Cause:** Previous run didn't complete before next scheduled run

**Fix:**
```python
dag = DAG(
    'rag_refresh',
    max_active_runs=1,  # Only one instance at a time
    catchup=False  # Don't backfill
)
```

---

### Failure 3: Memory Exhaustion

**Symptom:** `MemoryError: Cannot allocate memory`

**Cause:** Loading all documents into memory at once

**Fix:**
```python
# Process in batches, don't accumulate
for batch in chunks(files, batch_size=100):
    process_batch(batch)
    # Batch goes out of scope, memory freed
```

---

### Failure 4: Zombie Processes

**Symptom:** Orphaned processes consuming resources

**Cause:** No cleanup in finally blocks

**Fix:**
```python
import signal

try:
    process_documents()
finally:
    # Cleanup: kill process group
    os.killpg(os.getpgid(0), signal.SIGTERM)
```

---

### Failure 5: Silent Failures

**Symptom:** Pipeline reports success but data is incorrect

**Cause:** Swallowing exceptions, no validation

**Fix:**
```python
# Add validation
def validate_embeddings(embeddings):
    assert len(embeddings) > 0, "No embeddings generated"
    assert len(embeddings[0]) == 1536, "Dimension mismatch"
    return True
```

---

## Decision Card

### ✅ Use Airflow When:

- You have 500-50,000 documents
- Updates happen hourly or daily (batch-friendly)
- You have complex task dependencies
- You need parallel processing
- You have operational capacity (2+ person team)
- You can allocate 4+ GB RAM
- You need monitoring and alerting

### ❌ Don't Use Airflow When:

- You have <500 documents → **Use cron job**
- You need real-time (<1 min latency) → **Use Kafka**
- Simple linear pipeline → **Use Python script**
- Windows-only environment → **Use Prefect**
- <4GB RAM available → **Use serverless (Lambda)**
- Solo developer side project → **Too much overhead**

---

## Alternative Solutions

### Option 1: Cron Job (Free, 5 min setup)

**Best for:** <500 documents, solo developer

```bash
# Add to crontab: Run daily at 2 AM
0 2 * * * cd /app && python incremental_update.py >> logs/cron.log 2>&1
```

**Pros:** Zero overhead, no learning curve
**Cons:** No retry logic, no monitoring, no parallelization

---

### Option 2: Prefect (~$100/month)

**Best for:** Teams wanting modern Python tooling, 1K-50K documents

**Pros:** Modern API, better error handling, native Kubernetes
**Cons:** Smaller ecosystem, managed cloud costs $1,200+/year

---

### Option 3: AWS EventBridge + Lambda (~$30/month)

**Best for:** AWS-native shops, event-driven architecture

**Pros:** Serverless, scales automatically, pay-per-use
**Cons:** AWS lock-in, cold start latency, 15-minute timeout

---

### Option 4: Kafka + Stream Processing (~$220+/month)

**Best for:** Real-time requirements, >10K daily updates

**Pros:** True real-time (<1s latency), high-throughput
**Cons:** High complexity, requires dedicated team

---

## Cost Breakdown (Monthly, 10K Documents)

| Component | Cost |
|-----------|------|
| Compute (4 workers, 2GB each) | $30 |
| PostgreSQL database | $12 |
| OpenAI embeddings API | $50 |
| Pinecone vectors | $70 |
| Monitoring (Prometheus) | $12 |
| **Total** | **~$162/month** |

**Compare:**
- Cron job: ~$120/month (no orchestration costs)
- Prefect Cloud: ~$220/month (managed service)
- AWS Lambda: ~$30/month (serverless, but 15-min timeout)

---

## Troubleshooting

### Issue: "Configuration incomplete" message

**Solution:** Copy `.env.example` to `.env` and add your API keys

```bash
cp .env.example .env
# Edit .env and add:
# OPENAI_API_KEY=sk-...
# PINECONE_API_KEY=...
```

---

### Issue: Import errors

**Solution:** Install all dependencies

```bash
pip install -r requirements.txt
```

---

### Issue: "No changes detected" even after modifying files

**Solution:** The checksums file may be stale. Delete it:

```bash
rm data/checksums.json
```

---

### Issue: FastAPI server won't start

**Solution:** Check port 8000 isn't already in use

```bash
# Find process using port 8000
lsof -i :8000

# Use different port
uvicorn app:app --port 8001
```

---

## File Structure

```
ccc_l2_aug_practical/
├── L2_M2_DataPipelines_Orchestration.ipynb  # Main notebook (16 cells)
├── l2_m2_datapipelines_orchestration.py     # Core module functions
├── app.py                                    # FastAPI entrypoint
├── config.py                                 # Environment configuration
├── requirements.txt                          # Dependencies
├── .env.example                              # Environment template
├── tests_smoke.py                            # Smoke tests
├── README.md                                 # This file
└── data/
    ├── documents/                            # Sample documents
    │   ├── sample_document_1.txt
    │   ├── sample_document_2.txt
    │   └── sample_document_3.txt
    └── checksums.json                        # Change tracking
```

---

## Production Deployment

### Step 1: Install Airflow

```bash
pip install apache-airflow
airflow db init
```

### Step 2: Create DAG

Convert the notebook code into a DAG file and place in `~/airflow/dags/`

### Step 3: Configure Executor

For parallel processing, use CeleryExecutor:

```bash
# Install Redis
brew install redis  # macOS
sudo apt-get install redis-server  # Ubuntu

# Update airflow.cfg
executor = CeleryExecutor
broker_url = redis://localhost:6379/0
```

### Step 4: Start Services

```bash
# Terminal 1: Scheduler
airflow scheduler

# Terminal 2: Webserver
airflow webserver

# Terminal 3: Celery workers
airflow celery worker
```

### Step 5: Monitor

- Web UI: http://localhost:8080
- View DAG runs, task status, logs
- Set up email/Slack alerts

---

## Monitoring Checklist

**Critical Metrics:**
- ✅ Task execution duration (baseline vs. current)
- ✅ Error rate percentage (alert if >10% sustained)
- ✅ Worker availability (alert if down >2 minutes)
- ✅ Data freshness lag (alert if >2 hours behind)
- ✅ Queue depth (alert if backlog growing)

**Alert Thresholds:**

**Critical (immediate):**
- Pipeline failure
- Error rate >25% for 5+ minutes
- All workers down

**Warning:**
- Pipeline duration >1.5× expected
- Error rate >10% for 5+ minutes
- Data freshness lag >2 hours

---

## Next Module

**Module 5.3:** Advanced Monitoring & Observability
- Distributed tracing for RAG pipelines
- Cost tracking and optimization
- Performance profiling at scale

---

## Resources

- [Apache Airflow Documentation](https://airflow.apache.org/)
- [Prefect Documentation](https://docs.prefect.io/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

## The Bottom Line

**Airflow is heavyweight infrastructure.** It's the right tool for production data pipelines at scale (500-50K documents), but it's overkill for most side projects.

**Ask yourself:**
1. Do I really need orchestration, or just scheduling? (If just scheduling → cron)
2. Do I have the operational capacity to maintain it? (If no → managed service)
3. Is my scale large enough to justify the complexity? (If <500 docs → no)

**Remember:** The best tool is the simplest one that meets your requirements.

---

## License

Educational material for L2 Production RAG Systems course.

---

## Support

For issues or questions, please refer to the course documentation or raise an issue in the course repository.
