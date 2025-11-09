# Module 8.3: Regression Testing & CI/CD for RAG Systems

> **Automated quality assurance for RAG systems using GitHub Actions, DVC, and pytest-benchmark**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Purpose

Prevent production quality degradation by automating regression testing for RAG systems. Learn to detect performance, accuracy, and cost regressions before deployment using CI/CD pipelines, model versioning, and safe deployment patterns.

## Concepts Covered

- **Regression Testing**: Automated test suites for RAG quality metrics (faithfulness, relevancy, precision, latency, cost)
- **CI/CD for ML**: GitHub Actions workflows that block bad code from reaching production
- **Model Versioning with DVC**: Track models/embeddings/prompts like code with instant rollback capability
- **Safe Deployment**: Canary testing and automated rollback on quality degradation
- **Test Stability**: Handling flaky tests and calibrating thresholds to avoid false positives
- **Cost-Benefit Analysis**: Decision framework for when CI/CD is appropriate vs. overkill

## After Completing

You will be able to:
- Build pytest-based regression test suites that run in <5 minutes for fast CI feedback
- Set up GitHub Actions workflows that automatically test every pull request
- Version ML models with DVC and S3, enabling instant rollback to any previous version
- Implement canary deployments with automatic rollback on test failures
- Calibrate regression thresholds using historical data to target 2-5% false positive rates
- Make informed decisions about CI/CD adoption based on team size, deployment frequency, and budget

## Context in Track

**Prerequisites**: L1 M3 (Deployment), M8.1 (RAGAS Evaluation), M8.2 (A/B Testing)
**Next Module**: M8.4 (Human-in-the-Loop Evaluation)
**Level**: 2 (Intermediate)
**Duration**: 35 minutes

This module builds on RAGAS evaluation (M8.1) by automating quality checks in a CI/CD pipeline. It complements A/B testing (M8.2) by catching regressions before they reach production A/B experiments.

---

## Windows-first Commands

**Run API server:**
```powershell
$env:PYTHONPATH="$PWD"; uvicorn app:app --reload
```

**Run tests:**
```powershell
$env:PYTHONPATH="$PWD"; pytest -v tests/
```

**Or use helper scripts:**
```powershell
.\scripts\run_api.ps1    # Start API server
.\scripts\run_tests.ps1  # Run test suite
```

## Environment Variables

See `.env.example` for all required environment variables:
- `OPENAI_API_KEY` - Required for RAG query generation and evaluation
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - Required for DVC S3 storage
- `SKIP_INTEGRATION_TESTS` - Set to `true` to skip tests requiring external services
- CI/CD variables: `CI`, `CI_COMMIT_SHA`, `CI_COMMIT_BRANCH`, `CI_RUN_NUMBER`

---

## Overview

This module implements automated regression testing and CI/CD for RAG (Retrieval Augmented Generation) systems. It prevents the horror scenario where "minor" changes compound to cause 40% quality drops in production.

**Key Features:**
- 🧪 Regression test suite with 5 key metrics
- 🤖 GitHub Actions workflow for automated testing
- 📦 DVC model versioning with instant rollback
- 🚦 Safe deployment with canary testing
- 📊 Cost estimation and decision framework
- 🔧 Flaky test handling and threshold calibration

**Prerequisites:**
- Level 1 M3 (Deployment)
- M8.1 (RAGAS Evaluation)
- M8.2 (A/B Testing)

---

## Quickstart

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd ccc_l2_aug_practical

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run the Jupyter Notebook

```bash
jupyter notebook L2_M8_Regression_Testing_CICD.ipynb
```

The notebook incrementally builds through 9 sections covering all concepts.

### 3. Run Smoke Tests

```bash
pytest tests_smoke.py -v
```

### 4. Start the API Server

```bash
# Development mode
python app.py

# Production mode
uvicorn app:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### 5. Run CLI Examples

```bash
python l2_regression_testing_cicd.py
```

---

## How It Works

### The Problem

RAG systems are **fragile compound systems**. Three "small" changes:
1. Upgrade embedding model
2. Tweak prompt formatting
3. Adjust reranking threshold

Can compound into a **40% quality drop** discovered days later after thousands of bad answers reach users.

### The Solution: Automated Regression Testing

```
┌─────────────────────────────────────────────────────────────────┐
│                    CI/CD WORKFLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PR Created → GitHub Actions Triggered                         │
│       ↓                                                         │
│  Pull DVC-tracked models from S3                              │
│       ↓                                                         │
│  Run regression test suite (50 questions, ~3 min)             │
│       ↓                                                         │
│  Measure 5 metrics:                                            │
│    • Faithfulness (≥0.75)                                      │
│    • Answer Relevancy (≥0.70)                                  │
│    • Context Precision (≥0.65)                                 │
│    • P95 Latency (≤2000ms)                                     │
│    • Cost per Query (≤$0.01)                                   │
│       ↓                                                         │
│  Pass? → Allow merge ✅                                        │
│  Fail? → Block merge + Post PR comment ❌                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Regression Test Suite (`RegressionTestSuite`)

Tests RAG quality on every PR:
- Uses 50-question subset (fast CI) vs 500 questions (nightly)
- Measures all 5 key metrics
- Handles failures gracefully
- Calculates P95 latency (not average—catches tail latencies)

#### 2. GitHub Actions Workflow

Example `.github/workflows/regression-tests.yml`:

```yaml
name: RAG Regression Tests
on:
  pull_request:
  push:
    branches: [main, production]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: dvc pull
      - run: pytest tests/ --benchmark-only
```

#### 3. DVC Model Versioning (`DVCVersionManager`)

Version control for ML models:
- Track models/embeddings/prompts like code
- Store in S3 (not Git—models are large)
- Enable instant rollback to any version
- Team collaboration without conflicts

```bash
dvc init
dvc remote add -d s3storage s3://your-bucket/path
dvc add models/
git add models.dvc .gitignore
git tag v1.0.0
dvc push
```

#### 4. Safe Deployment (`SafeDeployment`)

Canary testing with auto-rollback:
- Test new version on 10 queries
- Rollback if pass rate <80%
- Prevents bad deployments

---

## Common Failures & Fixes

### ❌ Failure #1: CI Pipeline Too Slow (>10 minutes)

**Problem:** Full test suite takes 20+ minutes, developers context-switch
**Solution:** Separate fast CI (50 questions) from nightly eval (500 questions)

```python
# pytest.ini
[pytest]
markers =
    fast: Fast CI tests (50 questions)
    full: Full evaluation (500 questions)

# Run in CI: pytest -m fast
# Run nightly: pytest -m full
```

### ❌ Failure #2: Flaky Tests (Intermittent Failures)

**Problem:** Single-run tests sensitive to infrastructure variance
**Solution:** Run 5 times, use median, apply ±20% tolerance band

```python
handler = FlakyTestHandler(num_runs=5, tolerance_pct=20.0)
median, all_values = handler.run_stable_test(test_func)
```

### ❌ Failure #3: Wrong Regression Thresholds

**Problem:** Too sensitive → blocks every PR (false positives)
           Too loose → misses real regressions (false negatives)
**Solution:** Calibrate using historical data: `threshold = baseline - 2*std`

```python
calibrator = ThresholdCalibrator()
for value in historical_data:
    calibrator.add_measurement('faithfulness', value)

threshold = calibrator.calculate_threshold('faithfulness', num_std=2.0)
# Targets 2-5% false positive rate
```

### ❌ Failure #4: DVC Merge Conflicts

**Problem:** Simultaneous model changes → conflicting MD5 hashes
**Solution:** Test both versions, choose better faithfulness score

```python
resolver = DVCConflictResolver(test_suite)
winner = resolver.resolve_conflict('version_a', 'version_b', pipeline_factory)
```

### ❌ Failure #5: Rollback Failures (Previous Version Lost)

**Problem:** S3 lifecycle deleted old models before rollback needed
**Solution:** Configure S3 to retain minimum 10 versions for 90 days

```bash
# S3 lifecycle policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-dvc-bucket \
  --lifecycle-configuration file://lifecycle.json
```

---

## Decision Card: When to Use CI/CD

### ✅ USE When:

- Deploy **20-100 times/month**
- Team of **3-10 engineers**
- Budget **≥$150/month**
- Have product-market fit (stable requirements)
- Need production confidence before each deploy
- Can dedicate 20% time for CI/CD maintenance

### ❌ AVOID When:

- Deploy **<5 times/month** (manual testing more efficient)
- Team **<3 people** (maintenance overhead too high)
- Budget **<$50/month** (can't afford GitHub Actions + S3)
- **Pre-PMF** (requirements change too fast)
- Need **<100ms latency** (testing overhead unacceptable)
- Solo developer or 2-person team

### Alternative Approaches

| Approach | Best For | Cost | Setup Time |
|----------|----------|------|------------|
| **Manual Testing** | <3 people, <5 deploys/month | $0 | 0 hours |
| **Staged Rollouts** | 3-10 people, 10-50 deploys/month | $50/mo | 8 hours |
| **GitHub Actions CI/CD** | 3-10 people, 20-100 deploys/month | $150/mo | 16 hours |
| **Managed Platforms** | 10+ people, 100+ deploys/month | $2000/mo | 80+ hours |

---

## Cost Breakdown

### Small Scale (10 deploys/month)
- GitHub Actions: $20-30
- S3 Storage: $15-20
- API costs: $15-30
- **Total: $50-80/month**

### Medium Scale (50 deploys/month)
- GitHub Actions: $80-100
- S3 Storage: $30-40
- API costs: $40-60
- **Total: $150-200/month**

### Large Scale (100+ deploys/month)
- GitHub Actions: $300-400
- S3 Storage: $80-100
- API costs: $120-300
- **Total: $500-800/month**
- 💡 Consider managed platform at this scale

**Cost Optimization Tips:**
- Use GPT-3.5 instead of GPT-4 for testing (3x cheaper)
- Cache embeddings to reduce API calls
- Run full eval nightly, not on every PR
- Use self-hosted runners if >100 deploys/month

---

## API Endpoints

The FastAPI server provides REST endpoints:

### `GET /health`
Health check and service availability

### `POST /tests/run`
Run regression test suite
```json
{
  "test_data_path": "test_data/example_data.json",
  "use_subset": true
}
```

### `POST /costs/estimate`
Estimate CI/CD costs
```json
{
  "deploys_per_month": 50,
  "team_size": 5
}
```

### `POST /decision`
Get CI/CD recommendation
```json
{
  "deploys_per_month": 50,
  "team_size": 5,
  "budget_per_month": 300,
  "has_pmf": true
}
```

### `GET /versions`
List available DVC model versions

### `GET /metrics`
Prometheus metrics (if prometheus-client installed)

---

## Troubleshooting

### Issue: Tests failing with "OpenAI API key not set"

**Solution:** Copy `.env.example` to `.env` and add your OpenAI API key:
```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-your-key-here
```

### Issue: DVC operations failing

**Solution:** Initialize DVC and configure S3 remote:
```bash
dvc init
dvc remote add -d s3storage s3://your-bucket/dvc-storage
dvc remote modify s3storage region us-east-1
```

### Issue: CI pipeline timing out

**Solution:** Use subset testing and optimize test size:
- Reduce test subset to 30 questions
- Run full evaluation nightly instead of per-PR
- Use pytest-xdist for parallel execution

### Issue: High false positive rate

**Solution:** Recalibrate thresholds:
```bash
python -c "
from l2_regression_testing_cicd import ThresholdCalibrator
calibrator = ThresholdCalibrator()
# Add historical measurements...
thresholds = calibrator.get_recommended_thresholds()
print(thresholds)
"
```

---

## Project Structure

```
ccc_l2_aug_practical/
├── l2_regression_testing_cicd.py    # Core module with all functionality
├── config.py                         # Configuration management
├── app.py                            # FastAPI REST API
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
├── L2_M8_Regression_Testing_CICD.ipynb  # Interactive tutorial notebook
├── tests_smoke.py                    # Basic validation tests
├── README.md                         # This file
├── test_data/
│   └── example_data.json            # Sample test data (10 questions)
└── models/                          # DVC-tracked models (empty initially)
```

---

## Key Metrics & Thresholds

| Metric | Threshold | Description |
|--------|-----------|-------------|
| **Faithfulness** | ≥0.75 | Answer grounded in retrieved context |
| **Answer Relevancy** | ≥0.70 | Answer addresses the question |
| **Context Precision** | ≥0.65 | Quality of retrieved documents |
| **P95 Latency** | ≤2000ms | 95th percentile response time |
| **Cost per Query** | ≤$0.01 | API costs per query |

These thresholds should be **calibrated** to your specific system using historical data.

---

## Monitoring Requirements

### CI Pipeline Health
- CI duration P95 **<8 minutes** (target <5 minutes)
- Test flakiness **<5%** (rerun rate)
- PR block rate **2-5%** (false positive sweet spot)

### Quality Metrics Tracking
- Track baseline metrics over time
- Alert on threshold degradation
- Review calibration **quarterly**

---

## Team Responsibilities

- **3-5 people:** Rotating "CI shepherd" role (1 week rotations)
- **6-10 people:** 20% MLOps time allocation (1 person part-time)
- **10+ people:** Full-time MLOps engineer

---

## Next Steps

1. ✅ **Complete PractaThon Challenge:**
   - **Easy** (60 min): Basic workflow with 3 metrics, 20-question test set
   - **Medium** (90-120 min): Add latency/cost tests, DVC versioning, threshold calibration
   - **Hard** (4-5 hours): Production-grade with deployment automation, canary testing, conflict resolution

2. 📚 **Proceed to M8.4:** Human-in-the-Loop Evaluation

3. 🚀 **Production Deployment:**
   - Set up GitHub Actions workflow
   - Initialize DVC with S3 remote
   - Calibrate thresholds with baseline data
   - Configure monitoring and alerts

---

## References

- **Module Script:** `augmented_M8_VideoM8_3_Regression_Testing_CI_CD.md`
- **RAGAS Framework:** https://docs.ragas.io/
- **DVC Documentation:** https://dvc.org/doc
- **GitHub Actions:** https://docs.github.com/en/actions
- **pytest-benchmark:** https://pytest-benchmark.readthedocs.io/

---

## License

MIT License - see LICENSE file for details

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review the Jupyter notebook for detailed examples
3. Run smoke tests: `pytest tests_smoke.py -v`
4. Check logs in the FastAPI server output

---

**Module Duration:** 35 minutes
**Level:** 2
**Last Updated:** 2025-01-07
