# Module 7.1: Distributed Tracing with OpenTelemetry

**Request-level visibility for RAG systems using OpenTelemetry and Jaeger**

## Overview

This module implements distributed tracing for production RAG systems, providing detailed visibility into retrieval → reranking → generation pipelines. When aggregate metrics show P95 latency of 850ms but users report 4.2-second queries, distributed tracing enables debugging of specific slow requests.

### What You'll Learn

- Initialize OpenTelemetry tracer with production-ready BatchSpanProcessor
- Auto-instrument FastAPI for HTTP request tracing
- Add manual spans for RAG pipeline stages (retrieval, reranking, generation)
- Visualize traces in Jaeger UI
- Correlate traces with logs using trace IDs
- Configure sampling for production (10-50% to reduce overhead)
- Handle common failures (context propagation, storage overflow, high overhead)

### Key Trade-offs

✅ **Benefits:**
- Request-level debugging (why was THIS query slow?)
- Sub-millisecond timing precision per stage
- Trace-to-log correlation via trace_id
- Production-ready at 1K-10K req/day scale

❌ **Limitations:**
- Adds 10-20ms overhead at 100% sampling (1-2ms at 10%)
- Requires Jaeger infrastructure monitoring (disk, queries, memory)
- Storage scales quickly: 4-15GB/week at 10K+ req/day
- More expensive than metrics (10-100x cost)

💰 **Cost:**
- 4-8 hours implementation time
- $0/month for <2K req/day
- $20-50/month at 24K req/day (Elasticsearch needed)
- $200-500/month at 240K+ req/day (Tempo or managed APM)

### When NOT to Use

❌ Avoid if:
- <100 req/day (use structured logging instead)
- Single-service monolith (use profilers like py-spy)
- Budget <$50/month
- MVP phase (architecture changes frequently)
- >100K req/day without DevOps expertise (use managed APM)

✅ Use when:
- 500+ req/day with distributed system
- Need to debug latency issues across services
- Budget >$50/month or DevOps capacity available
- Post-MVP stable architecture

---

## Quickstart

### 1. Prerequisites

```bash
# Python 3.9+
python --version

# Docker (for Jaeger)
docker --version
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Jaeger

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:1.51
```

**Ports:**
- `16686`: Jaeger UI (http://localhost:16686)
- `4317`: OTLP gRPC collector
- `4318`: OTLP HTTP collector

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### 5. Run the Application

```bash
# FastAPI server with auto-instrumentation
python app.py
```

Visit:
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Jaeger UI:** http://localhost:16686

### 6. Send Test Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are GDPR compliance requirements?",
    "top_k": 10,
    "top_n": 5,
    "model": "gpt-4"
  }'
```

Response includes `trace_id` and `jaeger_ui_url` for viewing the trace.

### 7. View Trace in Jaeger

1. Open http://localhost:16686
2. Select service: `rag-compliance-copilot`
3. Click "Find Traces"
4. View waterfall: retrieval → reranking → generation

---

## How It Works

### Architecture Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /query
       ▼
┌─────────────────────────────────────────┐
│         FastAPI (Auto-Instrumented)     │ ◄── Creates parent HTTP span
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│        RAG Pipeline (Manual Spans)       │
│                                          │
│  1. pinecone.retrieve (200ms)            │
│     └─ embedding.generate (50ms)         │
│     └─ pinecone.query (150ms)            │
│                                          │
│  2. reranking.process (200ms)            │
│                                          │
│  3. llm.generate (800ms)                 │
│                                          │
│  Total: 1200ms                           │
└──────┬──────────────────────────────────┘
       │ Spans batched every 5 seconds
       ▼
┌─────────────────────────────────────────┐
│    BatchSpanProcessor (Async Export)    │
└──────┬──────────────────────────────────┘
       │ OTLP gRPC (port 4317)
       ▼
┌─────────────────────────────────────────┐
│         Jaeger (Storage + UI)            │
│  - Badger DB (default, 7-30 day TTL)     │
│  - Elasticsearch (production >10K/day)   │
└─────────────────────────────────────────┘
```

### Key Components

1. **Tracer Initialization** (`l2_m7_distributed_tracing_opentelemetry.py`)
   - Configures OpenTelemetry with OTLP exporter
   - Uses `BatchSpanProcessor` (async, low-overhead) not `SimpleSpanProcessor` (50-100ms latency)
   - Buffers up to 2048 spans, exports in batches of 512 every 5 seconds

2. **FastAPI Auto-Instrumentation** (`app.py`)
   - `FastAPIInstrumentor.instrument_app(app)` creates parent spans for all HTTP requests
   - Automatically captures method, path, status code, exceptions

3. **Manual RAG Spans** (`l2_m7_distributed_tracing_opentelemetry.py`)
   - Wrap retrieval, reranking, generation with `tracer.start_as_current_span()`
   - Capture attributes: result counts, model names, token usage, costs
   - Nested spans show detailed breakdowns

4. **Trace-Log Correlation** (`TraceContextLogger`)
   - Adds `trace_id` and `span_id` to log records
   - Enables jump from Jaeger → logs and vice versa

5. **Production Configuration** (`config.py`)
   - Environment-specific sampling: dev 100%, staging 50%, prod 10%
   - Graceful degradation if Jaeger unavailable

---

## Common Failures & Fixes

### 1. Missing Trace Context Propagation

**Symptom:** Two separate traces instead of one connected trace
**Cause:** Python threading doesn't auto-propagate OpenTelemetry context
**Fix:**

```python
from opentelemetry import context

current_context = context.get_current()
thread = threading.Thread(
    target=my_function,
    args=(data, current_context)
)
```

**Prevention:** Use `asyncio` instead of threading, install instrumentation packages

### 2. High Overhead (10-20% Latency)

**Symptom:** P95 latency jumps 850ms → 1020ms (+20%)
**Cause:** 100% sampling with fine-grained spans (per loop iteration)
**Fix:**

```python
# Reduce sampling to 10%
sampler = ParentBased(root=TraceIdRatioBased(0.1))
provider = TracerProvider(resource=resource, sampler=sampler)
```

**Result:** 850ms → 862ms (+1.4% acceptable)
**Prevention:** Start with 10-50% sampling, coarse spans (operations not loops)

### 3. Sampling Misses Critical Traces

**Symptom:** Search for slow request's trace_id → NOT FOUND
**Cause:** Head-based sampling (1%) decides before request completes
**Fix:** Use tail-based sampling via OpenTelemetry Collector, or force-sample errors:

```python
if is_error or latency_ms > 2000:
    # Always sample slow requests and errors
    with tracer.start_as_current_span("critical.operation", sampling_probability=1.0):
        process_request()
```

**Prevention:** Always sample errors (100%), use tail-based for slow requests

### 4. Jaeger Storage Overflow

**Symptom:** Jaeger UI hangs (30+ second queries), eventually OOM kills process
**Cause:** 10K traces/day × 30 days = 300K traces = 1.5GB disk, no cleanup
**Fix:**

```bash
# Configure TTL and maintenance
docker run jaegertracing/all-in-one:1.51 \
  -e BADGER_TTL=168h \
  -e BADGER_MAINTENANCE_INTERVAL=1h \
  --memory=2g
```

**Better:** Use Elasticsearch backend for production (columnar storage, faster queries)
**Prevention:** Set TTL from day 1 (7-30 days), monitor disk <80%, use sampling

### 5. Incomplete Span Coverage

**Symptom:** Total time (1200ms) > sum of spans (780ms), missing 420ms
**Cause:** HTTP client library not instrumented (e.g., httpx, requests)
**Fix:**

```bash
pip install opentelemetry-instrumentation-httpx
```

Or add manual spans:

```python
with tracer.start_as_current_span("external_api_call") as span:
    response = await client.post(...)
    span.set_attribute("api.status_code", response.status_code)
```

**Prevention:** Check OpenTelemetry registry for instrumentation, review traces for gaps

---

## Decision Card

### ✅ BENEFIT
Request-level visibility into retrieval → reranking → generation with sub-millisecond precision. Debug slow requests by seeing exactly where time went. Correlate traces with metrics and logs using trace IDs.

### ❌ LIMITATION
Adds 10-20ms overhead at 100% sampling (1-2ms at 10%). Requires Jaeger infrastructure monitoring (disk, queries, memory). At 10K+ req/day, storage becomes expensive and slow (4-15GB/week)—upgrade to Elasticsearch or managed APM.

### 💰 COST
- **Implementation:** 4-8 hours
- **Monthly:** $0 for <2K req/day, $20-50 at 24K req/day, $200-500 at 240K+ req/day
- **Alternative managed APM:** $200-1200/month
- **Complexity:** 4 dependencies, 1 service, ~150 lines code, 2-4 hours/month maintenance

### 🤔 USE WHEN
- 500+ req/day with distributed system
- Need to debug latency issues across services
- Multiple external APIs (retrieval, reranking, LLM)
- Budget >$50/month or DevOps capacity
- Team can invest 1 week in setup

### 🚫 AVOID WHEN
- <100 req/day (use structured logging)
- Single-service monolith (use profilers)
- <$50/month budget
- MVP phase (architecture changes frequently)
- >100K req/day without DevOps (use managed APM)

---

## Alternative Solutions

| Solution | Best For | Pros | Cons | Cost |
|----------|----------|------|------|------|
| **Managed APM** (Datadog, New Relic) | >10K req/day, budget >$200/mo | Zero maintenance, anomaly detection, 90-day retention | Vendor lock-in, cost scales with volume | $200-2000/mo |
| **Cloud Tracing** (AWS X-Ray, GCP Cloud Trace) | 1K-50K req/day, cloud-native | Free tier, native integration, no separate backend | Vendor lock-in, 30-day max retention | Free-$50/mo |
| **Structured Logging** | <100 req/day, limited budget | Zero infrastructure, no overhead, free | Manual correlation, no visualization | $0-10/mo |
| **Tempo** | >100K req/day, need long retention | Scales to 1M+ req/day, cheap object storage | Complex setup, requires DevOps | $50-200/mo |

---

## Troubleshooting

### No traces in Jaeger

**Check:**
1. Jaeger running? `docker ps | grep jaeger`
2. OTLP endpoint correct? `echo $OTLP_ENDPOINT` (should be `http://localhost:4317`)
3. Network connectivity? `telnet localhost 4317`
4. Wait 5+ seconds for batch export
5. Check logs for export errors

### Traces missing attributes

**Fix:**
- Ensure attributes set before span ends
- Check attribute types (strings, ints, floats, bools only)
- Verify no exceptions during span creation

### High memory usage

**Causes:**
- `MAX_QUEUE_SIZE` too high (default: 2048 spans × 5KB = 10MB)
- No TTL configured (spans accumulate indefinitely)

**Fix:**
```bash
# Set TTL and memory limit
docker run ... -e BADGER_TTL=168h --memory=2g
```

### Slow Jaeger UI queries

**Causes:**
- Too many traces (>100K in database)
- No indexes on trace_id
- Badger DB not optimized for large datasets

**Fix:**
- Reduce retention (7 days instead of 30)
- Upgrade to Elasticsearch backend
- Increase sampling (10% instead of 50%)

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run smoke tests
pytest tests_smoke.py -v

# Run with integration tests (requires Jaeger)
SKIP_INTEGRATION_TESTS=false pytest tests_smoke.py -v

# Check coverage
pytest tests_smoke.py --cov=l2_m7_distributed_tracing_opentelemetry --cov-report=html
```

---

## Production Deployment Checklist

- [ ] TTL configured (7-30 days): `BADGER_TTL=168h`
- [ ] Sampling rate set (10-50%): `SAMPLING_RATE=0.1`
- [ ] BatchSpanProcessor (not SimpleSpanProcessor)
- [ ] Disk monitoring + alerts (<80%)
- [ ] Backup/restore tested (S3 weekly export)
- [ ] Load test overhead (<5% increase acceptable)
- [ ] PII redaction enabled (`redact_sensitive_attributes`)
- [ ] TLS configured (`OTLP_INSECURE=false`)
- [ ] Team trained on Jaeger UI
- [ ] Runbooks documented

---

## Configuration Reference

### Environment-Specific Settings

```yaml
development:
  sampling_rate: 1.0    # 100% - trace everything
  retention_days: 3     # Short retention to save disk
  batch_size: 512       # Standard batching

staging:
  sampling_rate: 0.5    # 50% - balance visibility and cost
  retention_days: 7     # 1 week for issue investigation
  batch_size: 512

production:
  sampling_rate: 0.1    # 10% - reduce overhead from 15ms to 1.5ms
  retention_days: 30    # 30 days for compliance
  batch_size: 1024      # Larger batches for efficiency
```

### Cost Optimization

1. **Reduce sampling:** 50% → 10% = 80% storage savings
2. **Lower retention:** 30 days → 7 days = 75% storage savings
3. **Use object storage:** S3/GCS for old traces ($5/mo vs $50/mo disk)

### Monitoring Requirements

**Must track:**
- Disk usage <80% (alert 80%, critical 90%)
- Trace ingestion rate (matches 10% of request rate)
- Query latency <5s (if slower, hitting disk limits)
- Memory usage <80%

**Alert on:**
- Disk >80% → trigger cleanup
- Trace ingestion = 0 → OTLP connection broken
- Query latency >10s → Elasticsearch needs scaling
- CPU >80% sustained → capacity needed

---

## Project Structure

```
.
├── l2_m7_distributed_tracing_opentelemetry.py  # Core tracing module
├── app.py                                       # FastAPI entrypoint
├── config.py                                    # Configuration management
├── requirements.txt                             # Dependencies
├── .env.example                                 # Environment template
├── example_data.json                            # Sample queries and traces
├── tests_smoke.py                               # Smoke tests
├── README.md                                    # This file
└── L2_M7_Distributed_Tracing_with_OpenTelemetry.ipynb  # Interactive notebook
```

---

## Next Steps

### Module 7.2: Advanced Observability Patterns
- Custom metrics from traces
- Trace-based alerts
- Service dependency mapping
- Cost attribution per customer

### Further Reading
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [Tail-Based Sampling](https://opentelemetry.io/docs/concepts/sampling/#tail-sampling)

---

## Support

**Issues:** Report bugs or request features in the repository issues
**Questions:** Check Jaeger docs or OpenTelemetry community
**Production Support:** Consider managed APM for 24/7 support

---

## License

MIT License - See LICENSE file for details

---

**Built with TVH Framework v2.0** - Teaching with Honesty, acknowledging trade-offs, limitations, and alternative solutions.
