# Module 8.2: A/B Testing for RAG Improvements

Scientifically validate RAG system improvements before full production rollout using controlled experiments with statistical rigor.

## Overview

This module implements a complete A/B testing framework for RAG systems that allows you to:
- Test configuration changes (chunk size, top_k, temperature) on a subset of traffic
- Measure impact with statistical significance (p < 0.05)
- Minimize risk by exposing only 10-50% of users to experimental variants
- Make evidence-based deployment decisions with confidence intervals

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
# Edit .env with your settings (optional for demo mode)
```

### 2. Run the Notebook

```bash
jupyter notebook L2_M8_AB_Testing_for_RAG_Improvements.ipynb
```

### 3. Run the Demo

```bash
# Test the module
python l2_m8_ab_testing_rag_improvements.py

# Check configuration
python config.py

# Run smoke tests
python tests_smoke.py

# Start FastAPI server
python app.py
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Create experiment
curl -X POST http://localhost:8000/experiment \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_id": "exp_001",
    "name": "Chunk Size Test",
    "control_config": {"chunk_size": 512},
    "treatment_config": {"chunk_size": 1024},
    "traffic_split": 0.5
  }'

# Execute query with A/B testing
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are GDPR requirements?",
    "user_id": "user_123"
  }'
```

## How It Works

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                            │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Experiment Manager   │ ◄── Check active experiments
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   Traffic Splitter    │ ◄── Assign user to variant
            │  (MD5 hashing)        │     (consistent assignment)
            └───────────┬───────────┘
                        │
                ┌───────┴────────┐
                │                │
                ▼                ▼
        ┌──────────────┐  ┌──────────────┐
        │   Control    │  │  Treatment   │
        │ chunk_size   │  │ chunk_size   │
        │   = 512      │  │   = 1024     │
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┬────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   RAG Execution       │
            │  (retrieval + LLM)    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  RAGAS Evaluation     │ ◄── Measure metrics
            │  (faithfulness, etc)  │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Store Results        │ ◄── Database/in-memory
            └───────────┬───────────┘
                        │
           After N samples accumulated
                        │
                        ▼
            ┌───────────────────────┐
            │ Statistical Analyzer  │ ◄── Welch's t-test
            │  - p-value            │     Bootstrap CI
            │  - confidence interval│
            │  - recommendation     │
            └───────────┬───────────┘
                        │
                ┌───────┴────────┐
                │                │
         p < 0.05?          p >= 0.05?
                │                │
                ▼                ▼
        ┌──────────────┐  ┌──────────────┐
        │  Roll Out    │  │ Keep Control │
        │  Treatment   │  │  or Keep     │
        │  Gradually   │  │  Running     │
        └──────────────┘  └──────────────┘
```

### Statistical Analysis Flow

```
Collect Data (1000+ samples per variant)
           │
           ▼
Calculate Descriptive Stats
  - Control mean: 0.8234
  - Treatment mean: 0.8467
  - Difference: +0.0233 (2.83%)
           │
           ▼
Welch's t-test (independent samples)
  - Doesn't assume equal variance
  - Handles different sample sizes
  - Returns: p-value = 0.0127
           │
           ▼
Bootstrap Confidence Interval
  - Resample 10,000 times
  - Calculate 95% CI: [0.0051, 0.0415]
  - Robust to non-normal distributions
           │
           ▼
Decision Logic
  - p < 0.05 AND CI doesn't include 0?
    → Significant!
  - difference > 0?
    → Treatment wins
  - Else → Control wins or Inconclusive
```

## Common Failures & Fixes

### Failure 1: Insufficient Sample Size
**Symptom:** p-value always >0.05, can't detect real improvements
**Fix:** Calculate required sample size first with `calculate_required_sample_size()`
**Prevention:** Wait for 1000+ samples per variant before analyzing

### Failure 2: Selection Bias
**Symptom:** Control has older users, treatment has newer users
**Fix:** Use cryptographic hashing (MD5) for assignment, not simple modulo
**Prevention:** Validate distribution after first 100 assignments

### Failure 3: Multiple Testing Problem
**Symptom:** Running 20 experiments, finding 3 "winners" (1 expected by chance)
**Fix:** Apply Bonferroni correction: adjusted_alpha = 0.05 / 20 = 0.0025
**Prevention:** Limit concurrent experiments to 3-5 max

### Failure 4: Premature Rollout
**Symptom:** Roll out after 2 days, effect disappears after week
**Fix:** Wait for minimum sample size AND run for full week (weekend patterns)
**Prevention:** Pre-register stopping criteria before looking at results

## Decision Card

### ✅ BENEFIT
Validate RAG improvements scientifically before full rollout. Measure real user impact with statistical rigor (p<0.05). Catch regressions on 10-50% of traffic instead of 100%.

### ❌ LIMITATION
Requires 1000+ requests per variant for significance (3-7 days at 1K/day traffic). Cannot detect small improvements (<2%) without massive samples (10K+). Adds 25-50ms latency for variant lookup.

### 💰 COST
Implementation: 8-12 hours. Monthly: $5-10 at 1K/day traffic (database), scales to $50-80 at 10K/day. Complexity: ~800 LOC, 4 database tables, requires understanding t-tests.

### 🤔 USE WHEN
- You have 1000+ daily queries
- Single-factor experiments
- Change impact is unclear (needs data)
- Can tolerate 10-50% of users seeing potentially worse variant

### 🚫 AVOID WHEN
- Traffic <1000/day → Use before/after comparison
- Testing multiple factors → Use sequential testing
- Change is obviously better/worse → Use shadow mode
- Can't risk user impact → Use shadow mode

## Troubleshooting

### "No active experiments" warning
- Create an experiment first with `ExperimentManager.create_experiment()`
- Check experiment status is 'running' not 'paused' or 'completed'

### "Insufficient sample size" in analysis
- Expected! Need 1000+ samples per variant
- Check how many samples collected: `analyzer.analyze_experiment()` shows counts
- Estimate time: (2000 samples) / (queries_per_day) = days needed

### Assignment distribution not 50/50
- Small deviations OK (48/52 is fine)
- Large deviations (40/60) indicate bug in hashing
- Verify hash function includes both user_id AND experiment_id

### p-value keeps changing when I check daily
- Normal! P-values fluctuate during experiment
- Wait for minimum sample size before making decisions
- Don't "peek" multiple times (causes p-hacking)

### Database connection errors
- Check DATABASE_URL in .env
- Module works without database (in-memory mode)
- For production, set up PostgreSQL and run schema from notebook

### "⚠️ Skipping API calls (no keys/service)"
- Normal in demo mode without LLM API keys
- Module simulates RAG responses for testing
- To use real RAG, set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env

## File Structure

```
ccc_l2_aug_practical/
├── l2_m8_ab_testing_rag_improvements.py   # Main module implementation
├── L2_M8_AB_Testing_for_RAG_Improvements.ipynb  # Tutorial notebook
├── config.py                               # Configuration management
├── app.py                                  # FastAPI web service
├── tests_smoke.py                          # Smoke tests
├── requirements.txt                        # Python dependencies
├── .env.example                            # Environment template
├── example_data.json                       # Sample test data
└── README.md                               # This file
```

## Next Module

**M8.3: Continuous Monitoring & Alerting**
Learn to detect regressions in production before users complain.

## References

- Source script: `M8_2_AB_Testing_RAG_I.md`
- Statistical methods: Welch's t-test, Bootstrap resampling
- Traffic splitting: Consistent hashing with MD5
- Multiple testing correction: Bonferroni, Benjamini-Hochberg

## Support

For issues or questions:
1. Check Troubleshooting section above
2. Review notebook for detailed examples
3. Run `python tests_smoke.py` to verify setup
4. Check logs with LOG_LEVEL=DEBUG in .env

---

**Built with TVH Framework v2.0** - Emphasizing trade-offs, limitations, and failure modes.
