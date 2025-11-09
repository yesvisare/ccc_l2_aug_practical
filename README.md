# Module 6.1: PII Detection & Redaction

Enterprise security module for protecting sensitive data before it reaches vector databases or LLM APIs.

## Learning Arc

### Purpose

Prevent sensitive data leakage in RAG systems by detecting and redacting Personally Identifiable Information (PII) at ingest and query time. Protects SSNs, emails, phone numbers, and custom entity types before they reach vector stores or LLM APIs, ensuring compliance with privacy regulations while maintaining system utility.

### Concepts Covered

- **Regex baseline detection** - Fast pattern matching for common PII formats (SSN, credit cards, phones)
- **Optional NER/Presidio integration** - Context-aware entity recognition with confidence scoring
- **Configurable entity sets** - Customize which PII types to detect based on compliance needs
- **Redaction modes** - Mask (preserve format), hash (audit trails), tokenize, or label entities
- **Overlap handling** - Resolve conflicts when multiple patterns match the same span
- **Simple evaluation** - Measure precision/recall on sample datasets
- **Demo mode** - Offline regex-only operation without external dependencies

### After Completing

- Run PII detection locally on documents and text streams
- Apply policy-based redaction with configurable strategies
- Export brief summary reports showing entity counts and processing metrics
- Operate offline using regex-only mode when advanced models unavailable

### Context in Track

This module sits in **M6: Enterprise Security & Compliance**, protecting both indexing (preventing PII from entering vector stores) and serving (sanitizing query inputs/outputs). Integrates with M5 data pipelines for pre-processing and feeds into M7 monitoring for compliance auditing.

## Overview

This module implements automated PII detection and redaction using Microsoft Presidio, combining:
- **Regex pattern matching** (fast, ~10ms per document)
- **Named Entity Recognition** via spaCy (context-aware, 50-100ms overhead)
- **Confidence scoring** (0.0-1.0 thresholds)

**Achieves 85-92% accuracy** - suitable for internal knowledge bases but NOT for HIPAA/PCI-DSS compliance contexts requiring 99%+ accuracy.

### Performance Characteristics

- **Processing overhead**: 80-150ms per document
- **False positive rate**: 10-15% at balanced settings (threshold 0.5)
- **Memory footprint**: 2GB minimum RAM, 730MB dependency overhead
- **Scalability**: Economical for 5K-10K documents/day

### When NOT to Use

1. **Real-time systems** requiring <200ms latency (NER overhead too high)
2. **High-compliance contexts** (HIPAA: $1.5M penalties, PCI-DSS) requiring 99%+ accuracy
3. **Small datasets** (<500 documents) where manual review is faster than automated setup

## Quickstart

### 1. Installation

```bash
# Clone repository
git clone <repository-url>
cd ccc_l2_aug_practical

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model (WARNING: ~560MB download)
python -m spacy download en_core_web_lg
```

### 2. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (optional - has sensible defaults)
nano .env
```

Key configuration options:
- `PII_CONFIDENCE_THRESHOLD`: 0.0-1.0 (default: 0.5)
- `PII_REDACTION_STRATEGY`: masking, replacement, or hashing (default: replacement)
- `MAX_WORKERS`: Parallel processing workers (default: 4)

### 3. Run the Service

**Windows (PowerShell):**
```powershell
# Using script (recommended)
.\scripts\run_api.ps1

# Or manually
powershell -c "$env:PYTHONPATH='$PWD;$PWD\src'; uvicorn app:app --reload"
```

**Unix/Mac:**
```bash
# Using script
./scripts/run_api.sh

# Or manually
PYTHONPATH="$PWD/src:$PYTHONPATH" uvicorn app:app --reload
```

Server starts on http://localhost:8000
API docs available at http://localhost:8000/docs

### 4. Quick Test

```bash
# Health check
curl http://localhost:8000/health

# Detect PII
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact John at john@example.com or call 555-1234"}'

# Redact PII
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "SSN: 123-45-6789", "strategy": "replacement"}'
```

### 5. Run Tests

**Windows (PowerShell):**
```powershell
# Using script (recommended)
.\scripts\run_tests.ps1

# Or manually
powershell -c "$env:PYTHONPATH='$PWD;$PWD\src'; pytest -q"
```

**Unix/Mac:**
```bash
# Using script
./scripts/run_tests.sh

# Or manually
PYTHONPATH="$PWD/src:$PYTHONPATH" pytest tests/ -v
```

## How It Works

### Architecture Diagram (Text)

```
┌─────────────────┐
│  Input Document │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Presidio Analyzer Engine   │
│  ┌─────────────────────────┐│
│  │ 1. Regex Patterns       ││  Fast: ~10ms
│  │    - SSN, Phone, Email  ││
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ 2. spaCy NER            ││  Slower: 50-100ms
│  │    - Context-aware      ││  More accurate
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ 3. Custom Recognizers   ││
│  │    - Employee IDs       ││
│  │    - Policy Numbers     ││
│  └─────────────────────────┘│
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Confidence Scoring         │
│  (Threshold: 0.5 default)   │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Presidio Anonymizer        │
│  ┌─────────────────────────┐│
│  │ Strategy: Masking       ││  → "****-**-****"
│  │ Strategy: Replacement   ││  → "<SSN>"
│  │ Strategy: Hashing       ││  → "a3f2c8..."
│  └─────────────────────────┘│
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│ Redacted Output │
└─────────────────┘
```

### Three Redaction Strategies

1. **Masking** - Preserves format structure
   - Input: `"SSN: 123-45-6789"`
   - Output: `"SSN: ***-**-****"`
   - Use case: When format context is important

2. **Replacement** - Semantic placeholders
   - Input: `"SSN: 123-45-6789"`
   - Output: `"SSN: <US_SSN>"`
   - Use case: Best for LLM context preservation

3. **Hashing** - Consistent anonymization
   - Input: `"SSN: 123-45-6789"`
   - Output: `"SSN: e5f2a8c1b9d3..."`
   - Use case: Audit trails requiring re-identification

## Common Failures & Fixes

### 1. False Positives Breaking Valid Content

**Problem**: Email addresses in code samples or test data get redacted, breaking functionality.

**Symptoms**:
```python
# Before: test@example.com
# After: <EMAIL_ADDRESS>  ← Breaks test code
```

**Fix**: Implement whitelisting for known test domains
```python
from l2_m6_pii_detection_redaction import create_whitelist_patterns

patterns = create_whitelist_patterns()
# Includes: @example.com, @test.com, already-redacted placeholders
```

**Cost**: 10-15% of detections are false positives at threshold 0.5

---

### 2. 2-3x Processing Slowdown

**Problem**: NER analysis adds 80-150ms per document, doubling processing time.

**Symptoms**:
- Baseline processing: 50ms per document
- With PII detection: 130-200ms per document

**Fix**: Use parallel processing for batch operations
```python
from l2_m6_pii_detection_redaction import process_documents_parallel

results = process_documents_parallel(
    documents=doc_list,
    detector=detector,
    max_workers=4  # 3.7x speedup on 1000 docs
)
```

**Trade-off**: Memory usage increases with worker count (4 workers ≈ 8GB RAM)

---

### 3. Incomplete Variant Detection

**Problem**: Variations in PII formatting bypass detection.

**Symptoms**:
- Detects: `"123-45-6789"`
- Misses: `"123 45 6789"` (spaces instead of dashes)
- Misses: `"one two three four five"` (spelled out)

**Fix**: Extended regex patterns (included in module)
```python
# Detects multiple formats
SSN_VARIANTS = [
    r'\b\d{3}-\d{2}-\d{4}\b',  # With dashes
    r'\b\d{3}\s\d{2}\s\d{4}\b',  # With spaces
    r'\b\d{9}\b'  # No separators
]
```

**Limitation**: Spelled-out numbers still bypass detection (requires custom ML model)

---

### 4. Log Masking Bypasses

**Problem**: PII leaks into logs via exception tracebacks, not just message text.

**Symptoms**:
```python
# Log message: Redacted correctly
# Exception traceback: "ValueError: Invalid SSN: 123-45-6789"  ← LEAK!
```

**Fix**: Custom formatter masks PII in tracebacks
```python
from l2_m6_pii_detection_redaction import setup_logging

logger = setup_logging(enable_masking=True)
# Masks PII in both messages AND exception text
```

**Coverage**: SSN, phone, email, credit cards

---

### 5. GDPR Deletion Verification Failures

**Problem**: Eventual consistency means immediate verification fails.

**Symptoms**:
```
Deletion executed: doc-123
Verification failed: doc-123 still exists (checked immediately)
```

**Fix**: Exponential backoff retry logic (2, 4, 8, 16, 32 seconds)
```python
from l2_m6_pii_detection_redaction import GDPRDeletionService

service = GDPRDeletionService(max_retries=5)
success, message = service.delete_and_verify(
    document_id="doc-123",
    deletion_callback=delete_func,
    verification_callback=verify_func
)
```

**Wait times**: Up to 62 seconds total (2+4+8+16+32)

## Decision Card

### Should You Use This Approach?

| Scenario | Use Automated PII Detection? | Rationale |
|----------|------------------------------|-----------|
| Internal knowledge base (5K docs) | YES | 85-92% accuracy acceptable; cost-effective |
| Customer support chatbot (<200ms SLA) | NO | 80-150ms overhead violates latency budget |
| Financial compliance (PCI-DSS) | NO | 8-15% miss rate = compliance violations |
| HR documents (GDPR, 10K docs/day) | YES with human review | Automated + sampling reduces cost |
| Real-time transaction monitoring | NO | Use managed service (AWS Macie, 95-98% accuracy) |
| Research dataset anonymization | MAYBE | Consider differential privacy instead |

### Cost-Performance Matrix

| Volume | Self-Hosted (This Module) | Managed Service (AWS Macie) |
|--------|---------------------------|-----------------------------|
| 100 docs/day | ~$96/month | ~$120/month |
| 1K docs/day | ~$180/month | ~$210/month |
| 10K docs/day | ~$890/month | ~$1,040/month |
| 100K docs/day | Not recommended | ~$4,200/month |

**Break-even point**: ~10K documents/day

### Confidence Threshold Guidelines

| Threshold | Precision | Recall | False Positives | Use Case |
|-----------|-----------|--------|-----------------|----------|
| 0.3 | 70-80% | High | 20-30% | Exploratory analysis |
| 0.5 | 85-92% | Medium | 10-15% | **Recommended default** |
| 0.7 | 92-96% | Low | 5-8% | High-stakes with review |
| 0.9 | 96-98% | Very Low | 2-4% | Compliance contexts |

## Troubleshooting

### Issue: "Presidio not available"

**Cause**: Dependencies not installed

**Fix**:
```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

---

### Issue: High memory usage (>4GB)

**Cause**: spaCy model loaded in memory + parallel workers

**Fix**:
1. Reduce `MAX_WORKERS` in `.env` (default: 4 → try 2)
2. Use smaller spaCy model: `en_core_web_sm` (less accurate, 90% memory savings)

---

### Issue: Slow processing (>200ms per document)

**Cause**: NER overhead on large documents

**Fix**:
1. Reduce confidence threshold (fewer entities = faster)
2. Limit entity types (detect only critical PII)
```python
detector = PIIDetector(
    entity_types=["US_SSN", "CREDIT_CARD", "EMAIL_ADDRESS"]
)
```

---

### Issue: False negatives (PII not detected)

**Cause**:
- Confidence threshold too high
- Custom PII format not recognized

**Fix**:
1. Lower threshold: 0.5 → 0.3 (increases false positives)
2. Add custom recognizer:
```python
from l2_m6_pii_detection_redaction import CustomRecognizerFactory

recognizer = CustomRecognizerFactory.create_employee_id_recognizer()
detector = PIIDetector(custom_recognizers=[recognizer])
```

## API Reference

### Core Module: `l2_m6_pii_detection_redaction.py`

**PIIDetector**
```python
detector = PIIDetector(
    confidence_threshold=0.5,
    custom_recognizers=None,
    entity_types=None
)

# Detect only
entities = detector.detect(text)

# Detect and redact
result = detector.redact(text, strategy=RedactionStrategy.REPLACEMENT)
```

**Parallel Processing**
```python
from l2_m6_pii_detection_redaction import process_documents_parallel

results = process_documents_parallel(
    documents=["text1", "text2"],
    detector=detector,
    strategy=RedactionStrategy.MASKING,
    max_workers=4
)
```

**GDPR Deletion**
```python
from l2_m6_pii_detection_redaction import GDPRDeletionService

service = GDPRDeletionService(max_retries=5)
success, msg = service.delete_and_verify(
    document_id="doc-123",
    deletion_callback=delete_func,
    verification_callback=verify_func
)
```

### REST API Endpoints

**Health Check**
```bash
GET /health
→ {"status": "ok", "presidio_available": true}
```

**Detect PII**
```bash
POST /query
{
  "text": "Contact John at john@example.com",
  "confidence_threshold": 0.5  # optional
}
→ {"entities": [...], "count": 1}
```

**Redact PII**
```bash
POST /redact
{
  "text": "SSN: 123-45-6789",
  "strategy": "replacement"  # masking, replacement, hashing
}
→ {"redacted_text": "SSN: <US_SSN>", "entities_found": [...]}
```

**Batch Redaction**
```bash
POST /redact/batch
{
  "texts": ["doc1", "doc2"],
  "strategy": "replacement",
  "max_workers": 4
}
→ {"results": [...], "total_documents": 2}
```

## Alternative Approaches

### 1. Managed Cloud Services

**Options**: AWS Macie, Google DLP, Azure Information Protection

**Pros**:
- 95-98% accuracy (vs 85-92% for Presidio)
- No infrastructure management
- Compliance certifications

**Cons**:
- $1-5 per 1,000 documents
- Vendor lock-in
- Network latency for API calls

**Best for**: >10K documents/day, compliance-critical contexts

---

### 2. Manual Human Review

**Pros**:
- 100% accuracy (human-verified)
- Flexible judgment on edge cases

**Cons**:
- $320-990 per 1,000 documents (time cost)
- Doesn't scale beyond ~500 documents
- Human error still possible

**Best for**: <500 documents, high-stakes legal contexts

---

### 3. Pre-Processing at Data Source

**Pros**:
- Zero processing overhead (validated on input)
- Prevents PII from entering system

**Cons**:
- Users circumvent with creative formatting
- Doesn't protect legacy data
- Requires UI/UX changes

**Best for**: Controlled SaaS products with form inputs

---

### 4. Differential Privacy

**Pros**:
- Provable privacy guarantees
- Enables analytics on sensitive data

**Cons**:
- 20-40% accuracy loss on embeddings
- Complex tuning of epsilon/delta parameters
- Research-level implementation

**Best for**: Analytics/research on aggregate data, not document redaction

## Next Steps

After completing Module 6.1, proceed to:

- **Module 6.2**: Access Control & Authorization (role-based document access)
- **Module 6.3**: Audit Logging & Compliance (tamper-proof audit trails)
- **Module 7.1**: Production Deployment (scaling to enterprise workloads)

## License

[Your license here]

## Support

For issues or questions:
- File an issue on GitHub
- Check documentation at [docs link]
- Review the Jupyter notebook: `L2_M6_PII_Detection_Redaction.ipynb`
