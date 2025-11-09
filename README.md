# Module 5.3: Data Quality & Validation

Production-ready data quality validation for RAG systems. Prevents indexing 30-40% low-quality content that wastes storage, compute, and degrades retrieval accuracy.

## Purpose

This module enforces input/document quality for RAG pipelines before indexing. It validates chunk schema, detects nulls/type mismatches, checks range/length bounds, identifies duplicates, and guards chunk size and embedding length. By applying quality gates early, we prevent bad data from poisoning the vector database and degrading retrieval accuracy.

## Concepts Covered

- **Schema Checks**: Validate required fields and data types for chunks and metadata
- **Null/Type/Format Validation**: Ensure text content is non-empty and properly encoded
- **Range/Length Bounds**: Enforce optimal chunk sizes (200-800 characters) and detect outliers
- **Duplicate Detection**: Identify exact and near-duplicate chunks using MinHash LSH (O(n) complexity)
- **Referential Checks**: Validate metadata consistency (source, date, section fields)
- **Chunk-Size Guards**: Prevent oversized or undersized chunks from entering the pipeline
- **Metrics & Reporting**: Track quality pass rates, deduplication rates, and drift scores for monitoring

## After Completing This Module

- **Run batch validation locally**: Process example data without any external API keys or services
- **Read pass/fail metrics**: View quality scores, deduplication results, and drift detection summaries in console output
- **Export validation reports**: Generate local reports with quality statistics and failure reasons
- **Operate entirely offline**: All validation runs locally on your machine with no cloud dependencies

## Context in Track (L2: Production Data Management)

This module (M5.3) is part of Level 2's Production Data Management track. It follows **M5.1 (Incremental Indexing)** and **M5.2 (Data Pipelines & Orchestration)**, adding quality gates before data enters the vector index. M5.3 prevents bad data from poisoning your RAG system by filtering low-quality chunks, removing duplicates, and detecting data drift. The validated data then flows to downstream modules for indexing and evaluation, ensuring only high-quality content reaches production.

## Overview

This module implements three quality pillars:

1. **Chunk Quality (Intrinsic)** - Scores chunks 0-100 based on information density, semantic completeness, readability, metadata quality, and length appropriateness
2. **Duplicate Detection (Relational)** - Identifies exact and near-duplicates using MinHash LSH with O(n) complexity
3. **Data Drift (Temporal)** - Monitors statistical distribution shifts using Kolmogorov-Smirnov test

**Problem Solved:** Production RAG systems often index corrupted PDFs, duplicates, and boilerplate-heavy content without verification, leading to wasted resources and poor retrieval quality.

**Key Benefits:**
- Prevents 20-40% low-quality chunks from indexing
- Catches duplicates with ~2-5% false negative rate
- Surfaces data quality issues in <30 seconds
- Adds only 15-30% pipeline overhead

## Quickstart

### Installation

```bash
# Clone repository
git clone <repository-url>
cd ccc_l2_aug_practical

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env
# Edit .env with your settings
```

### Quick Test

**Windows (PowerShell):**
```powershell
# Run smoke tests
powershell -c "$env:PYTHONPATH='src;.'; pytest tests/ -q"

# Run API server
powershell -c "$env:PYTHONPATH='src;.'; uvicorn app:app --reload"

# Run validation demo
.\scripts\run_validate.ps1
```

**Linux/Mac:**
```bash
# Run smoke tests
PYTHONPATH=src:. pytest tests/ -v

# Run API server
PYTHONPATH=src:. uvicorn app:app --reload

# Run validation demo
./scripts/run_validate.sh
```

**Using Scripts:**
```bash
# Windows
.\scripts\run_tests.ps1
.\scripts\run_api.ps1
.\scripts\run_validate.ps1

# Linux/Mac
./scripts/run_tests.sh
./scripts/run_api.sh
./scripts/run_validate.sh
```

### Basic Usage

**Quality Scoring:**
```python
from m5_3_data_quality import ChunkQualityScorer, ChunkMetadata

scorer = ChunkQualityScorer(min_score=70.0)

score = scorer.score_chunk(
    "Machine learning requires validation for generalization...",
    ChunkMetadata(source="ml.pdf", date="2024-01", section="validation")
)

print(f"Score: {score.total_score}, Passed: {score.passed}")
# Score: 85.2, Passed: True
```

**Duplicate Detection:**
```python
from m5_3_data_quality import DuplicateDetector

detector = DuplicateDetector(threshold=0.85)

chunks = [
    ("chunk1", "The quick brown fox..."),
    ("chunk2", "The quick brown fox..."),  # Duplicate
    ("chunk3", "Machine learning is...")   # Unique
]

unique_ids, dup_info = detector.deduplicate_batch(chunks)
print(f"Unique: {len(unique_ids)}, Duplicates: {len(dup_info)}")
# Unique: 2, Duplicates: 1
```

**Drift Detection:**
```python
from m5_3_data_quality import DataDriftDetector

detector = DataDriftDetector(significance_level=0.05, drift_threshold=0.15)

# Set baseline from historical data
detector.set_baseline(
    quality_scores=[75, 80, 78, 82, 79] * 10,
    chunk_lengths=[500, 520, 480, 510, 490] * 10,
    information_density=[85, 87, 83, 86, 84] * 10
)

# Detect drift in current batch
result = detector.detect_drift(
    quality_scores=[60, 65, 62, 63, 61] * 10,  # Degraded
    chunk_lengths=[500, 510, 490, 505, 495] * 10,
    information_density=[68, 70, 66, 69, 67] * 10
)

print(f"Drift detected: {result['drift_detected']}")
print(f"Recommendations: {result['recommendations']}")
```

### API Usage

```bash
# Start server
python app.py

# Score chunks
curl -X POST http://localhost:8000/quality/score \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [
      {
        "chunk_id": "chunk1",
        "text": "Machine learning models require careful validation...",
        "metadata": {"source": "ml.pdf", "date": "2024-01", "section": "validation"}
      }
    ],
    "min_score": 70.0
  }'

# Detect duplicates
curl -X POST http://localhost:8000/duplicates/detect \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [
      {"chunk_id": "chunk1", "text": "The quick brown fox..."},
      {"chunk_id": "chunk2", "text": "The quick brown fox..."}
    ],
    "threshold": 0.85
  }'

# Full validation pipeline
curl -X POST http://localhost:8000/pipeline/validate \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [...],
    "min_quality_score": 70.0,
    "similarity_threshold": 0.85
  }'
```

## Environment Variables

Configure the module via `.env` file (copy from `.env.example`). All variables are **optional** - the module runs offline without any external services.

### Quality Scoring
- `MIN_QUALITY_SCORE` (default: 70.0) - Minimum quality score threshold (0-100) for chunks to pass validation
- `OPTIMAL_LENGTH_MIN` (default: 200) - Minimum optimal chunk length in characters
- `OPTIMAL_LENGTH_MAX` (default: 800) - Maximum optimal chunk length in characters

### Duplicate Detection
- `SIMILARITY_THRESHOLD` (default: 0.85) - Jaccard similarity threshold for near-duplicate detection (0-1)
- `NUM_PERMUTATIONS` (default: 128) - Number of MinHash permutations (higher = more accurate but slower)

### Data Drift Detection
- `SIGNIFICANCE_LEVEL` (default: 0.05) - P-value threshold for statistical significance in K-S test
- `DRIFT_THRESHOLD` (default: 0.15) - Minimum distribution shift to flag as drift (0-1, represents 15%)
- `MIN_DRIFT_SAMPLES` (default: 50) - Minimum samples required for drift detection

### Alert Thresholds (for monitoring)
- `ALERT_MIN_PASS_RATE` (default: 60.0) - Alert if quality pass rate drops below this percentage
- `ALERT_MAX_DRIFT_SCORE` (default: 0.25) - Alert if drift score exceeds this threshold
- `ALERT_MAX_DEDUP_RATE` (default: 25.0) - Alert if deduplication rate exceeds this percentage
- `ALERT_MAX_PIPELINE_MINUTES` (default: 45) - Alert if pipeline duration exceeds this in minutes

### Processing (optional optimization)
- `ENABLE_MULTIPROCESSING` (default: false) - Enable parallel processing for quality scoring
- `NUM_WORKERS` (default: 8) - Number of worker processes for multiprocessing
- `BATCH_SIZE` (default: 1000) - Batch size for processing chunks

### External Services (optional, not required for offline operation)
- `GRAFANA_API_KEY` - Grafana API key for dashboard integration (optional)
- `GRAFANA_URL` - Grafana instance URL (optional)
- `AIRFLOW_API_KEY` - Airflow API key for pipeline orchestration (optional)
- `AIRFLOW_URL` - Airflow instance URL (optional)

**Offline Behavior:** The module runs entirely offline without any API keys. It processes `example_data.json` locally, outputs validation metrics to console, and can export reports to local files. No cloud services are required.

## How It Works

### Architecture Diagram (Text)

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Ingestion Pipeline                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. CHUNK QUALITY SCORING (Intrinsic)                       │
│  ┌────────────────────────────────────────────────┐         │
│  │ ChunkQualityScorer                             │         │
│  │ • Information Density (30%)                    │         │
│  │ • Semantic Completeness (25%)                  │         │
│  │ • Readability (20%)                            │         │
│  │ • Metadata Quality (15%)                       │         │
│  │ • Length Appropriateness (10%)                 │         │
│  │                                                 │         │
│  │ Input: 10,000 chunks → Output: 7,500 passed    │         │
│  │ (75% pass rate, reject worst 25%)              │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. DUPLICATE DETECTION (Relational)                        │
│  ┌────────────────────────────────────────────────┐         │
│  │ DuplicateDetector (MinHash LSH)                │         │
│  │ • O(n) complexity vs O(n²) pairwise            │         │
│  │ • Jaccard similarity on tokenized text         │         │
│  │ • Threshold: 0.85 (85% similarity)             │         │
│  │ • ~2-5% false negative rate acceptable         │         │
│  │                                                 │         │
│  │ Input: 7,500 chunks → Output: 6,000 unique     │         │
│  │ (20% dedup rate, 1,500 duplicates removed)     │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. DATA DRIFT DETECTION (Temporal)                         │
│  ┌────────────────────────────────────────────────┐         │
│  │ DataDriftDetector (K-S Test)                   │         │
│  │ • Compare current vs baseline distribution     │         │
│  │ • Test quality, length, density separately     │         │
│  │ • Significance level: 0.05                     │         │
│  │ • Drift threshold: 0.15 (15% shift)            │         │
│  │                                                 │         │
│  │ Output: Alerts + Recommendations               │         │
│  │ "Quality degraded -17 points, check sources"   │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Index to Vector Database (Pinecone)             │
│              6,000 validated, unique chunks                  │
└─────────────────────────────────────────────────────────────┘
```

### Quality Scoring Algorithm

Each chunk is scored 0-100 across five weighted dimensions:

1. **Information Density (30%)**: Penalizes boilerplate patterns (e.g., "click here," "subscribe") and high word repetition
2. **Semantic Completeness (25%)**: Checks for complete sentences vs fragments; penalizes mid-sentence cuts
3. **Readability (20%)**: Validates encoding quality and sentence length (optimal: 10-25 words/sentence)
4. **Metadata Quality (15%)**: Confirms presence of source, date, section fields
5. **Length Appropriateness (10%)**: Optimal range 200-800 characters

**Failure Reasons:**
- "High boilerplate or repetition detected" (density < 60)
- "Incomplete sentences" (completeness < 60)
- "Poor readability" (readability < 60)
- "Missing metadata" (metadata < 60)
- "Chunk length outside optimal range" (length < 60)

### Duplicate Detection Algorithm

Uses MinHash LSH (Locality-Sensitive Hashing) for efficient approximate duplicate detection:

1. **Tokenize** text into words
2. **Create MinHash** signature (128 permutations default)
3. **Index** in LSH for fast candidate retrieval
4. **Calculate Jaccard similarity** for candidates
5. **Flag duplicates** if similarity ≥ threshold (0.85 default)

**Key Trade-off:** Probabilistic algorithm may miss ~2-5% duplicates, but avoids O(n²) exhaustive comparison. For RAG, this is acceptable—perfect recall isn't worth 100x slowdown.

### Drift Detection Algorithm

Uses Kolmogorov-Smirnov (K-S) two-sample test to compare distributions:

1. **Set baseline** from historical metrics (quality scores, lengths, density)
2. **Collect current batch** metrics
3. **Run K-S test** for each metric independently
4. **Flag drift** if p-value < 0.05 AND K-S statistic > 0.15
5. **Generate recommendations** based on which metrics drifted

**Alert Thresholds:**
- Quality degradation > 10 points
- Length shift > 30%
- Density drop > 15 points

## Common Failures & Fixes

### Failure 1: False Positive Duplicates

**Problem:** High similarity threshold (0.95) flags "training by Dec 31, 2024" vs "2025" as duplicate.

**Symptoms:**
- Dedup rate suddenly >25%
- Alert: `dedup_rate_percent > 25.0`
- Log: "Found 3,000 duplicates for 5,000 chunks"

**Fix:**
1. Use standard 0.85 threshold (not 0.95)
2. Add date-aware filtering if timestamps change frequently
3. Monitor dedup rate (alert if >25%)

```python
# Bad
detector = DuplicateDetector(threshold=0.95)  # Too strict

# Good
detector = DuplicateDetector(threshold=0.85)  # Standard
```

### Failure 2: Miscalibrated Quality Thresholds

**Problem:** `min_score=90` rejects 70-80% of valid chunks (too strict).

**Symptoms:**
- Pass rate <30%
- Alert: `quality_pass_rate_percent < 60`
- Most chunks fail with "Poor readability" or similar

**Fix:**
1. Analyze real data distribution first
2. Set threshold at 10th-20th percentile
3. Reject worst 10-20% only, not top performers

```python
# Analyze your data first
scores = [scorer.score_chunk(chunk) for chunk in sample_chunks]
percentile_20 = np.percentile([s.total_score for s in scores], 20)

# Set threshold accordingly
scorer = ChunkQualityScorer(min_score=percentile_20)  # e.g., 65-75
```

### Failure 3: Drift Detection Sensitivity

**Problem:** `significance_level=0.10`, `drift_threshold=0.05` fires false alarms on natural variation.

**Symptoms:**
- Drift alerts every hour
- Alert fatigue
- Log: "Drift detected!" for minor fluctuations

**Fix:**
1. Use 0.05 significance level (standard)
2. Threshold 0.15 (15% shift, not 5%)
3. Require minimum 50 samples
4. Implement 6-hour cooldown between alerts

```python
# Bad
detector = DataDriftDetector(significance_level=0.10, drift_threshold=0.05)

# Good
detector = DataDriftDetector(significance_level=0.05, drift_threshold=0.15)
```

### Failure 4: Dashboard Performance Degradation

**Problem:** Plotting 1M metrics over 30 days causes 30+ second timeouts.

**Symptoms:**
- Grafana dashboards timeout
- Prometheus query duration >10s
- Alert: `dashboard_load_time > 30s`

**Fix:**
1. Batch metric flushes (every 60s, not per-chunk)
2. Use Prometheus recording rules for aggregations
3. Limit Grafana queries to <2000 data points (downsample)

```python
# Bad - per-chunk metrics
for chunk in chunks:
    chunks_processed.labels(status="passed").inc()  # 10K calls!

# Good - batch metrics
passed_count = sum(1 for s in scores if s.passed)
chunks_processed.labels(status="passed").inc(passed_count)  # 1 call
```

### Failure 5: Quality Scoring Bottleneck

**Problem:** Serial processing 50K chunks takes 280 seconds (4.5 minutes).

**Symptoms:**
- Pipeline duration >45 minutes
- Alert: `pipeline_duration_minutes > 45`
- CPU usage <20% (underutilized)

**Fix:**
1. Enable multiprocessing (8 workers = 8x speedup)
2. Batch operations (process 1000 chunks at a time)
3. Cache identical chunks (avoid re-scoring)

```python
# Set in .env or config
ENABLE_MULTIPROCESSING=true
NUM_WORKERS=8
BATCH_SIZE=1000
```

## Decision Card

### ✅ Use This Approach When:

- Processing 10K-500K chunks/day
- Diverse data sources (web scraping, PDFs, user uploads)
- Duplicate rate >10% historically
- Team size: 2+ engineers
- Storage/compute costs matter
- Retrieval quality degradation observed

### 🚫 Avoid This Approach When:

**Scenario 1 - Early MVP (<500 documents, changing >30% weekly)**
- **Problem:** Calibration overhead exceeds benefits
- **Use instead:** Manual review (Alternative 1)
- **Cost:** $500-2000/month human time vs $25-120/month automation + 2-4 hours/week tuning

**Scenario 2 - Real-time ingestion (<5 second latency required)**
- **Problem:** Quality scoring adds 15-30% overhead
- **Use instead:** Sampling validation (Alternative 3) - validate 10-15% only
- **Trade-off:** 95% quality vs 99.9% quality, but meets latency

**Scenario 3 - Curated sources (peer-reviewed publications, <1% bad data rate)**
- **Problem:** Automation costs exceed bad-data costs
- **Use instead:** Skip quality validation; MinHash dedup only
- **Savings:** 50% less pipeline time

**Scenario 4 - Multi-tenant (different quality standards per customer)**
- **Problem:** Complex per-tenant calibration
- **Use instead:** Managed platform with per-tenant config (Alternative 2)
- **Cost:** $500-2000/month but handles multi-tenancy

**Scenario 5 - Cost-constrained (quality validation exceeds bad-data costs)**
- **Problem:** GPU pipeline budget tight
- **Use instead:** Async validation on separate CPU-only pipeline
- **Savings:** Run validation overnight on cheaper instances

### 💰 Cost Breakdown

| Scale | Chunks/Day | Compute Cost/Month | Changes Needed |
|-------|------------|--------------------|-----------------
| Small | 10K | $15 | None |
| Medium | 100K | $80 | Multiprocessing (8 workers), Prometheus recording rules |
| Large | 1M+ | $400-600 | Distributed deduplication, streaming architecture |

**Setup Cost:** 2-3 days initial implementation + 1-2 weeks calibration
**Ongoing Maintenance:** 2-4 hours/week threshold tuning, alert management

### 📊 Performance Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Quality Pass Rate | 70-85% | <60% |
| Deduplication Rate | 5-20% | >25% or 0% |
| Drift Score | <0.20 | >0.25 |
| Pipeline Duration | <30 min | >45 min |

## Alternatives

### Alternative 1 - Manual Review
- **Cost:** $500-2000/month human time
- **Best for:** <5K chunks, regulatory compliance requiring human judgment
- **Trade-off:** Catches semantic issues automation misses; doesn't scale

### Alternative 2 - Managed Platforms (Monte Carlo, Soda, Great Expectations Cloud)
- **Cost:** $500-2000/month subscription
- **Best for:** <3 person teams, multi-source data, need solution by end of week
- **Trade-off:** Vendor lock-in; less customization; higher cost at scale

### Alternative 3 - Sampling Validation (10-15% validation)
- **Cost:** $40/month (80% less compute)
- **Best for:** 500K+ chunks, acceptable 95% quality (vs 99%+)
- **Trade-off:** Misses rare edge cases (1% slip-through rate)

### Alternative 4 - Embedding-Based Semantic Deduplication
- **Cost:** $3-10/month (OpenAI embeddings API)
- **Best for:** Multi-lingual content, semantic duplicates >20%, paraphrase detection
- **Trade-off:** 5-10x slower than MinHash; catches paraphrases MinHash misses

## Troubleshooting

### Import Errors

```bash
# Missing dependencies
pip install -r requirements.txt

# Python version issues (requires 3.8+)
python --version  # Should be 3.8+
```

### Config Errors

```python
# ValueError: MIN_QUALITY_SCORE must be between 0 and 100
# Fix: Check .env file
MIN_QUALITY_SCORE=70.0  # Not 700 or -10

# ValueError: SIMILARITY_THRESHOLD must be between 0 and 1
SIMILARITY_THRESHOLD=0.85  # Not 85
```

### API Errors

```bash
# Port already in use
# Fix: Change port or kill existing process
python app.py --port 8001

# 500 Internal Server Error
# Fix: Check logs for details
tail -f logs/app.log  # Or check console output
```

### Performance Issues

```bash
# Slow processing
# Fix: Enable multiprocessing
# In .env:
ENABLE_MULTIPROCESSING=true
NUM_WORKERS=8

# High memory usage
# Fix: Reduce batch size
BATCH_SIZE=500  # Instead of 1000
```

### Drift Detection Not Working

```python
# "No baseline set" error
# Fix: Set baseline first
detector.set_baseline(historical_quality, historical_lengths, historical_density)

# "Insufficient samples" error
# Fix: Need minimum 50 samples
# Accumulate more data before checking drift
```

## Monitoring

### Prometheus Metrics

Enable in `.env`:
```
ENABLE_PROMETHEUS=true
PROMETHEUS_PORT=8000
```

**Metrics exposed:**
- `chunks_processed_total{status="passed|failed_quality|duplicate"}` - Counter
- `chunk_quality_score` - Histogram (distribution)
- `quality_pass_rate_percent` - Gauge
- `deduplication_rate_percent` - Gauge
- `data_drift_score` - Gauge

**Query examples:**
```promql
# Pass rate over time
rate(chunks_processed_total{status="passed"}[5m]) /
rate(chunks_processed_total[5m]) * 100

# Quality score p50, p90, p99
histogram_quantile(0.50, chunk_quality_score)
histogram_quantile(0.90, chunk_quality_score)
histogram_quantile(0.99, chunk_quality_score)
```

### Grafana Dashboards

Import `grafana_dashboard.json` (if provided) or create custom:

**Panels to include:**
1. Quality pass rate (time series)
2. Deduplication rate (time series)
3. Drift score (time series)
4. Quality score distribution (histogram)
5. Pipeline duration (time series)
6. Alert status (stat panel)

### Alert Rules

**Alert 1: Low Pass Rate**
```yaml
alert: LowQualityPassRate
expr: quality_pass_rate_percent < 60
for: 10m
annotations:
  summary: "Quality pass rate below 60% for 10 minutes"
  action: "Check upstream data sources for corruption"
```

**Alert 2: High Drift**
```yaml
alert: DataDriftDetected
expr: data_drift_score > 0.25
for: 3 consecutive runs
annotations:
  summary: "Data distribution shift detected"
  action: "Review data sources and re-calibrate thresholds"
```

**Alert 3: Deduplication Anomaly**
```yaml
alert: DeduplicationAnomaly
expr: deduplication_rate_percent > 25 OR deduplication_rate_percent == 0
for: 5m
annotations:
  summary: "Dedup rate anomalous (>25% or 0%)"
  action: "Check detector configuration and source data"
```

## Next Steps

After completing this module, proceed to:

- **M5.4: Monitoring & Observability** - Build comprehensive monitoring dashboards
- **M6: Retrieval Optimization** - Improve search quality with hybrid retrieval
- **M7: Production Deployment** - Deploy to production with CI/CD

## Resources

- [Great Expectations Documentation](https://docs.greatexpectations.io/)
- [datasketch (MinHash LSH)](https://github.com/ekzhu/datasketch)
- [scipy.stats.ks_2samp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Documentation](https://grafana.com/docs/)

## License

[Your License Here]

## Support

For issues or questions:
- GitHub Issues: [repository-url]/issues
- Email: support@example.com
- Slack: #data-quality
