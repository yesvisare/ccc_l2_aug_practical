# Module 8.1: RAGAS Evaluation Framework

Systematic evaluation of RAG systems using RAGAS (RAG Assessment Framework) with four complementary metrics: **faithfulness**, **answer relevancy**, **context precision**, and **context recall**.

**Level:** 2 (Advanced RAG Systems)
**Duration:** 40 minutes
**Prerequisites:** Level 1 M4.3 (Basic metrics validation), working RAG system with monitoring

---

## 📋 Overview

RAGAS provides a production-ready framework for evaluating Retrieval-Augmented Generation systems. Unlike simple semantic similarity checks, RAGAS evaluates four distinct failure modes:

1. **Faithfulness** (0-1): Is the answer grounded in retrieved context? (catches hallucinations)
2. **Answer Relevancy** (0-1): Does the answer address the question? (catches tangential responses)
3. **Context Precision** (0-1): Are relevant chunks ranked highest? (catches ranking issues)
4. **Context Recall** (0-1): Did we retrieve all necessary information? (catches retrieval gaps)

**Key Features:**
- Golden test set creation and versioning
- LLM-as-judge evaluation using GPT-3.5-Turbo or GPT-4
- Automated evaluation pipelines with regression detection
- Domain-specific threshold evaluation (compliance, customer support, general)
- Batched processing with checkpoint recovery
- Cost estimation and tracking

---

## 🚀 Quickstart

### 1. Installation

```bash
cd m8_ragas_evaluation
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Run Jupyter Notebook

```bash
jupyter notebook L2_M8_RAGAS_Evaluation_Framework.ipynb
```

Or use the Python CLI:

```bash
python l2_m8_ragas_evaluation_framework.py
```

### 4. Run FastAPI Server

```bash
python app.py
# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 5. Run Tests

```bash
pytest tests_smoke.py -v
```

---

## 📁 Project Structure

```
m8_ragas_evaluation/
├── l2_m8_ragas_evaluation_framework.py  # Core module (800+ lines)
├── config.py                             # Configuration management
├── app.py                                # FastAPI REST API
├── tests_smoke.py                        # Smoke tests
├── requirements.txt                      # Python dependencies
├── .env.example                          # Environment template
├── example_data.json                     # Sample golden set
├── L2_M8_RAGAS_Evaluation_Framework.ipynb  # Complete tutorial notebook
├── README.md                             # This file
├── golden_sets/                          # Golden test sets storage
├── evaluation_results/                   # Evaluation results
└── checkpoints/                          # Checkpoint files
```

---

## 💡 How It Works

### The Evaluation Flow

```
┌─────────────────┐
│  Golden Set     │ ← 100-300 curated questions with ground truth
│  (Your Domain)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Your RAG       │ ← Query each question, collect answers + contexts
│  System         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RAGAS          │ ← Evaluate using GPT-3.5/GPT-4 as judge
│  Metrics        │   4 metrics × N questions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Results        │ ← Scores, regression detection, alerts
│  & Analysis     │
└─────────────────┘
```

### RAGAS Metrics Explained

| Metric | What It Measures | How It Works | Why It Matters |
|--------|------------------|--------------|----------------|
| **Faithfulness** | Is answer grounded in context? | Breaks answer into statements, checks each against retrieved chunks | Catches hallucinations that similarity misses |
| **Answer Relevancy** | Does answer address question? | Generates question variations from answer, checks similarity | Catches tangential but factually correct responses |
| **Context Precision** | Are relevant chunks ranked high? | Checks if relevant chunks appear at top positions | Identifies retrieval ranking issues |
| **Context Recall** | Did we retrieve everything needed? | Compares ground truth against retrieved chunks | Catches retrieval gaps and missing documents |

---

## 🔧 Usage Examples

### Creating a Golden Test Set

```python
from l2_m8_ragas_evaluation_framework import GoldenSetManager

manager = GoldenSetManager()

# Create questions
questions = [
    manager.create_question(
        question="What are GDPR data retention requirements?",
        ground_truth="GDPR requires retention for 6 years after employment ends...",
        contexts=[
            "GDPR Article 17 establishes right to erasure...",
            "Employee records must be retained for 6 years..."
        ],
        metadata={"category": "compliance", "complexity": "medium"}
    )
]

# Save golden set
filepath = manager.save_golden_set(questions, "compliance_rag", "v1")
```

### Running RAGAS Evaluation

```python
from l2_m8_ragas_evaluation_framework import RAGASEvaluator

evaluator = RAGASEvaluator(model_name="gpt-3.5-turbo")

# Evaluate your RAG system
results = evaluator.evaluate_system(
    questions=["What are GDPR requirements?"],
    generated_answers=["GDPR requires..."],
    retrieved_contexts=[["Context 1", "Context 2"]],
    ground_truths=["Expected answer..."]
)

# Print report
print(evaluator.generate_report(results))
```

### Domain-Aware Evaluation

```python
from l2_m8_ragas_evaluation_framework import DomainAwareEvaluator

# Compliance domain (strict faithfulness requirement)
evaluator = DomainAwareEvaluator(domain="compliance")

assessment = evaluator.evaluate_with_thresholds(results['scores'])

if not assessment['overall_passed']:
    for failure in assessment['failures']:
        print(f"❌ {failure['metric']}: {failure['severity']} severity")
```

### Automated Pipeline with Regression Detection

```python
from l2_m8_ragas_evaluation_framework import EvaluationPipeline

pipeline = EvaluationPipeline()

# Run complete pipeline
results = pipeline.run_pipeline(
    golden_set_name="compliance_rag",
    golden_set_version="v1",
    rag_query_func=your_rag_system.query,  # Your RAG query function
    save_results=True
)

# Check for regressions
if results['regression_analysis']['has_regression']:
    print("⚠️  Regression detected!")
    for reg in results['regression_analysis']['regressions']:
        print(f"  {reg['metric']}: {reg['delta']:.3f} drop")
```

---

## 🚨 Common Failures & Fixes

### Failure #1: Biased Golden Set

**Problem:** Test scores look great, but users complain. Your golden set only tests one query pattern.

**Example:**
- Golden set: 100 "What is Article X?" questions
- Production: Complex multi-part reasoning questions
- RAGAS: 0.89 faithfulness ✅
- Reality: 43% of queries failing ❌

**Fix:**
```python
# Analyze production query distribution
# Create representative golden set matching production (±10%)
# Include all query types: definitions, explanations, procedural, comparisons
```

### Failure #2: Metric Interpretation Errors

**Problem:** You're averaging metrics when faithfulness is binary. 0.45 faithfulness = 55% hallucinations!

**Fix:**
```python
# Use domain-specific thresholds (not averages)
# Compliance: faithfulness ≥ 0.90 (hard requirement)
# Treat faithfulness as pass/fail, not gradual
```

### Failure #3: Pipeline Timeouts

**Problem:** 300 questions × 4 metrics = 1200 API calls. Timeout loses all progress.

**Fix:**
```python
# Use ResilientEvaluator with batching (20 questions/batch)
# Automatic checkpointing and recovery
resilient = ResilientEvaluator(batch_size=20)
results = resilient.evaluate_with_batching(...)
```

### Failure #4: Missing Baselines

**Problem:** Is 0.75 good? Better than yesterday? No context = meaningless scores.

**Fix:**
```python
# EvaluationPipeline automatically tracks baselines
# Flags regressions >5% drop
# Tracks trends over time
```

### Failure #5: False Regression Alerts

**Problem:** LLM judge has ±3-5% natural variance. Alert fatigue from every small fluctuation.

**Fix:**
```python
# Only alert on drops >5% (above natural variance)
# Require 2-3 consecutive drops before alerting
# Use statistical significance for large sets
```

---

## 💰 Cost Analysis

### Monthly Operational Cost (100-question golden set)

| Component | Daily Runs | Weekly Runs | Notes |
|-----------|------------|-------------|-------|
| OpenAI API | $60-150 | $15-40 | GPT-3.5-Turbo (~$0.02 per 100Q) |
| MLflow (optional) | $10-30 | $10-30 | Tracking and visualization |
| Storage | $10-20 | $5-10 | Results history (30-90 days) |
| **Total** | **$80-200** | **$30-80** | |

**GPT-4 costs 15x more:** ~$30 per 100 questions vs. $2 for GPT-3.5-Turbo

### Time Investment

- **Golden set creation:** 40-80 hours for 100-300 questions (one-time)
- **Setup and integration:** 8-12 hours (one-time)
- **Maintenance:** 2-4 hours/month (updating golden set, analyzing results)

---

## 📊 Decision Framework: Should You Use RAGAS?

### ✅ USE WHEN

- **Scale:** 1000+ production queries/month with stable query patterns
- **Budget:** Can allocate $80-200/month for evaluation
- **Domain:** Factual/compliance-focused queries (not creative)
- **Need:** Systematic regression detection before users complain
- **Resources:** Team has 40-80 hours for golden set creation
- **Alternatives don't scale:** Manual review or simple comparison insufficient

### 🚫 AVOID WHEN

- **<100 queries/month** → Use manual review (1-2 hours/week)
- **Pre-product/market fit** → Query patterns unstable, golden set becomes obsolete
- **Creative/subjective answers** → Use user feedback and A/B testing instead
- **Budget <$1000/month total** → Evaluation overhead >20% of total budget
- **Domain-specific verification needed** → Medical/legal correctness requires expert review

### Alternative Approaches

| Approach | Best For | Cost | Pros | Cons |
|----------|----------|------|------|------|
| **Manual Review** | <100 queries/month | 1-2 hrs/week | Zero API cost, catches domain issues | Not systematic, doesn't scale |
| **Ground Truth Comparison** | Deterministic answers | ~$0.10/100Q | Fast, cheap | Misses hallucinations |
| **User Feedback** | Customer-facing | Zero | Real user signal | Lagging indicator, biased |
| **RAGAS** | 1000+ queries/month | $80-200/month | Systematic, scalable | High cost, LLM judge limitations |

---

## 🎯 Decision Card (Quick Reference)

**BENEFIT:** Systematic regression detection with 4 metrics that catch issues before users complain. Scales evaluation from 2 hours manual → 5 minutes automated. Industry-standard approach.

**LIMITATION:** Requires 40-80 hours golden set creation. LLM judge has 10-15% disagreement with humans on edge cases. Doesn't catch domain-specific correctness. $60-150/month ongoing cost.

**COST:**
- Time: 40-80h golden set + 12h setup + 2-4h/month maintenance
- Money: $80-200/month (API + MLflow + storage)
- Complexity: 4 new components, 800+ lines of code

**USE WHEN:** 1000+ queries/month, $80-200/month budget, factual domain, need systematic detection, 40-80h available for golden set

**AVOID WHEN:** <100 queries/month (manual review), pre-PMF (unstable patterns), creative answers (user feedback), tight budget (<$1000/month total)

---

## 🔍 Troubleshooting

### "⚠️ Skipping API calls (no keys/service)"

**Cause:** OPENAI_API_KEY not configured

**Fix:**
```bash
# Add to .env file
OPENAI_API_KEY=sk-your-key-here
```

### "TimeoutError: Request to OpenAI API timed out"

**Cause:** Large golden set (300+ questions) timing out

**Fix:**
```python
# Use batched evaluation with checkpointing
from l2_m8_ragas_evaluation_framework import ResilientEvaluator

resilient = ResilientEvaluator(batch_size=20)
results = resilient.evaluate_with_batching(...)
```

### "ValueError: Duplicate questions found in set"

**Cause:** Golden set contains duplicate questions

**Fix:** Deduplicate your questions before saving

### High Evaluation Costs

**Cause:** Running too frequently or using GPT-4

**Fix:**
- Switch to GPT-3.5-Turbo (15x cheaper)
- Run weekly instead of daily ($15-40/month vs. $60-150/month)
- Reduce golden set size (but maintain representativeness)

### Low Scores Across All Metrics

**Causes & Fixes:**
- **Faithfulness <0.7:** Hallucinating → Add "only use provided context" constraint
- **Answer Relevancy <0.7:** Tangential responses → Review system message
- **Context Precision <0.7:** Bad ranking → Check hybrid search alpha, reranking
- **Context Recall <0.7:** Missing info → Review indexing, adjust retrieval k

---

## 📚 API Reference

### Core Classes

#### `GoldenSetManager`
Manages golden test set creation and versioning.

```python
manager = GoldenSetManager(storage_path="./golden_sets")
question = manager.create_question(question, ground_truth, contexts, metadata)
filepath = manager.save_golden_set(questions, name, version)
questions = manager.load_golden_set(name, version)
```

#### `RAGASEvaluator`
Evaluates RAG systems using RAGAS metrics.

```python
evaluator = RAGASEvaluator(model_name="gpt-3.5-turbo")
results = evaluator.evaluate_system(questions, answers, contexts, ground_truths)
report = evaluator.generate_report(results)
```

#### `DomainAwareEvaluator`
Domain-specific threshold evaluation.

```python
evaluator = DomainAwareEvaluator(domain="compliance")  # or "customer_support", "general"
assessment = evaluator.evaluate_with_thresholds(scores)
```

#### `ResilientEvaluator`
Batched evaluation with checkpoint recovery.

```python
resilient = ResilientEvaluator(batch_size=20, checkpoint_dir="./checkpoints")
results = resilient.evaluate_with_batching(questions, answers, contexts, ground_truths)
```

#### `EvaluationPipeline`
Automated pipeline with regression detection.

```python
pipeline = EvaluationPipeline(results_dir="./evaluation_results")
results = pipeline.run_pipeline(golden_set_name, golden_set_version, rag_query_func)
```

### REST API Endpoints

When running `python app.py`:

- `GET /health` - Health check
- `GET /config` - Current configuration
- `POST /golden-sets` - Create golden set
- `GET /golden-sets/{name}/{version}` - Retrieve golden set
- `POST /evaluate` - Run RAGAS evaluation
- `POST /pipeline/run` - Run evaluation pipeline
- `GET /metrics` - Prometheus metrics (if enabled)

API docs: http://localhost:8000/docs

---

## 🔗 Next Steps

1. **Complete this module:**
   - Work through the Jupyter notebook
   - Create your domain-specific golden set (100+ questions)
   - Run evaluation on your RAG system
   - Set up nightly pipeline

2. **Next modules:**
   - Module 8.2: A/B Testing for RAG Systems
   - Module 8.3: Regression Testing in CI/CD
   - Module 8.4: Human-in-the-Loop Evaluation

3. **Production deployment:**
   - Integrate with your monitoring (Prometheus + Grafana)
   - Set up alerting for regressions (>5% drop)
   - Schedule nightly evaluations
   - Document runbooks for common failures

---

## 📖 References

- [RAGAS Documentation](https://docs.ragas.io/)
- [RAGAS Paper](https://arxiv.org/abs/2309.15217)
- Source: Video M8.1 Script - augmented_M8_VideoM8_1_RAGAS_Evaluatio.md
- Level 1 M4.3: Basic Validation Metrics (prerequisite)
- Level 1 M2.3: Monitoring & Observability (integration)

---

## 📝 License

Part of Level 2 RAG Systems Course - Module 8: Evaluation & Continuous Quality

---

**Questions or issues?** Open an issue or refer to the complete Jupyter notebook walkthrough.
