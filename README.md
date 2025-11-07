# Module 8.4: Human-in-the-Loop (HITL) Evaluation

Production-ready implementation of human-in-the-loop evaluation for RAG systems. Integrates human feedback into automated evaluation pipelines to close the quality gap between technical metrics and real user satisfaction.

## Overview

Automated metrics alone create dangerous blind spots. A system showing "92% faithfulness and 88% relevance" might have 15% negative user feedback—revealing that technically accurate responses don't guarantee helpfulness.

This module implements a complete HITL pipeline:
1. **Feedback Collection**: Capture thumbs up/down, ratings, and comments
2. **Active Learning**: Prioritize 20-50 queries daily for human review using uncertainty sampling + diversity clustering
3. **Label Studio Integration**: Structured annotation UI for multi-dimensional evaluation
4. **Inter-Annotator Agreement (IAA)**: Measure labeling consistency (target: >0.70)
5. **Feedback Loop Closure**: Route human labels back to system improvements

## Quick Start

### Installation

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration
```

### Run the API

```bash
# Start FastAPI server
python app.py

# Or with uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Run Smoke Tests

```bash
python tests_smoke.py
```

### Explore the Notebook

```bash
jupyter notebook L2_M8_Human_in_the_Loop_Evaluation.ipynb
```

## How It Works

```
┌─────────────────┐
│  User Queries   │
│   & Responses   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│   1. Feedback Collection    │
│   (Thumbs/Ratings/Comments) │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  2. Active Learning Select  │
│     • Uncertainty Sampling  │
│     • Negative FB Boost     │
│     • Diversity Clustering  │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   3. Label Studio Review    │
│   (Human Annotation)        │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   4. IAA Measurement        │
│   (Cohen's κ / Kripp's α)   │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  5. Feedback Loop Closure   │
│    • Aggregate Labels       │
│    • Extract Training Data  │
│    • Retrain System         │
└─────────────────────────────┘
```

## API Usage Examples

### Submit Feedback

```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "q_001",
    "feedback_type": "thumbs_down",
    "rating": 2,
    "comment": "Response was too generic"
  }'
```

### Select Queries for Annotation

```bash
curl -X POST http://localhost:8000/select-for-annotation \
  -H "Content-Type: application/json" \
  -d @selection_request.json
```

### Calculate Inter-Annotator Agreement

```bash
curl -X POST http://localhost:8000/iaa/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "annotator_a": [1, 1, 0, 1, 0, 1],
    "annotator_b": [1, 1, 0, 1, 1, 1],
    "metric": "kappa"
  }'
```

## Common Failures & Fixes

### 1. Feedback Bias (Only unhappy users respond)

**Symptom**: 80% negative feedback despite good technical metrics

**Fix**:
- Add proactive sampling of neutral/positive queries
- Incentivize feedback (e.g., "Help us improve" popups)
- Compare to random baseline of annotated queries

### 2. Low Inter-Annotator Agreement (IAA < 0.70)

**Symptom**: Annotators disagree frequently

**Fix**:
- Refine annotation guidelines with concrete examples
- Add calibration sessions with gold-standard labels
- Remove ambiguous edge cases from training set
- Use majority vote (3+ annotators) for contentious cases

### 3. Active Learning Selects Wrong Queries

**Symptom**: Annotators waste time on trivial or duplicate queries

**Fix**:
- Increase diversity clustering (try `n_clusters=15-20`)
- Add deduplication based on semantic similarity
- Manual review of top-priority queue before sending to annotators
- Boost negative feedback more aggressively (`boost=0.7`)

### 4. Annotation Bottleneck

**Symptom**: Backlog grows faster than annotation capacity

**Fix**:
- Reduce daily target (e.g., 50 → 30 queries)
- Hire additional annotators or use Scale AI
- Simplify annotation task (remove optional fields)
- Automate pre-filtering (e.g., skip queries with confidence >0.95)

### 5. Feedback Loop Never Closes

**Symptom**: Annotations collected but system never improves

**Fix**:
- Schedule weekly retraining pipeline
- Set up automated alerts when high-confidence labels accumulate
- Create feedback dashboard showing improvement trends
- Integrate annotations into CI/CD regression tests (Module 8.3)

## Decision Card

### ✅ Use Human-in-the-Loop Evaluation When:

- **Volume**: 500+ queries/day
- **Product Stage**: Established product-market fit
- **Budget**: $750-$3K/month for annotations
- **Resources**: 2-3 expert annotators available
- **Ambiguity**: Subjective quality not captured by automated metrics

### ❌ Skip HITL Evaluation When:

- **Clear Ground Truth**: Automated evaluation (M8.1) sufficient
- **Low Volume**: <100 queries/day
- **MVP Phase**: Iterate rapidly without stale labels
- **No Annotators**: Can't access domain experts
- **Tight Budget**: Use simple feedback buttons only

### 🔀 Alternative Approaches:

1. **Managed Services**: Scale AI, Labelbox (faster, more expensive)
2. **Feedback Buttons Only**: Minimal annotation (5 min setup)
3. **Periodic Surveys**: Monthly batched audits (lower cost)
4. **Expert Review Sessions**: Scheduled, not continuous (2-4 hrs/week)

## Production Considerations

### Costs

| Component | Cost per Query | Monthly (50/day) |
|-----------|----------------|------------------|
| Annotation Labor | $0.50 - $2.00 | $750 - $3,000 |
| Label Studio Hosting | - | $50 - $200 |
| Storage (SQLite → Postgres) | - | $20 - $100 |
| **Total** | **$0.50 - $2.00** | **$820 - $3,300** |

### Monitoring Metrics

1. **Feedback Response Rate**: Target >5% of users
2. **IAA Trending**: Alert if drops below 0.70
3. **Annotation Velocity**: Track backlog growth
4. **Label Distribution**: Identify bias patterns (e.g., 90% positive)

### Scaling Considerations

- **SQLite → PostgreSQL**: For >10K feedback entries
- **Label Studio → Label Studio Enterprise**: For teams >5 annotators
- **Local K-means → HDBSCAN**: For large-scale diversity clustering
- **Batch Processing**: Run active learning nightly instead of real-time

## Troubleshooting

### Label Studio won't connect

```bash
# Check Label Studio is running
curl http://localhost:8080/api/health

# Verify API key in .env
echo $LABEL_STUDIO_API_KEY

# Test connection
python -c "from config import get_label_studio_client; print(get_label_studio_client())"
```

### SQLite database locked

```bash
# Check for stale connections
lsof feedback.db

# Switch to PostgreSQL for production
# Update config.py with postgresql:// connection string
```

### IAA calculation fails

```python
# Ensure annotations are same length
assert len(annotator_a) == len(annotator_b)

# Check for NaN values in Krippendorff's alpha
annotations = [[1, 2, np.nan], [1, 2, 3]]  # NaN handled automatically
```

## File Structure

```
.
├── l2_m8_hitl_evaluation.py      # Core implementation
├── app.py                         # FastAPI wrapper
├── config.py                      # Configuration management
├── requirements.txt               # Dependencies
├── .env.example                   # Environment template
├── example_data.json              # Sample dataset
├── tests_smoke.py                 # Smoke tests
├── README.md                      # This file
└── L2_M8_Human_in_the_Loop_Evaluation.ipynb  # Interactive tutorial
```

## Integration with Other Modules

- **M8.1 (RAGAS)**: Use HITL to validate automated metric accuracy
- **M8.2 (A/B Testing)**: A/B test annotation-driven improvements
- **M8.3 (CI/CD)**: Add high-confidence labels to regression test suite

## Next Steps

- **Module 8.5**: Production monitoring and alerting
- **Module 9**: Advanced RAG architectures (multi-hop, agents)

## Resources

- [Label Studio Documentation](https://labelstud.io/guide/)
- [Inter-Annotator Agreement Guide](https://en.wikipedia.org/wiki/Inter-rater_reliability)
- [Active Learning in NLP](https://arxiv.org/abs/2104.04514)

## License

MIT License - Free for educational and commercial use.

---

**Questions?** Open an issue or check the troubleshooting section above.
