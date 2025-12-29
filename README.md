# Module 7.2: Application Performance Monitoring

Deep code-level profiling with Datadog APM integrated with OpenTelemetry tracing.

## Overview

This module adds **Application Performance Monitoring (APM)** to complement your existing M7.1 OpenTelemetry tracing. While traces show WHICH span is slow, APM shows WHY it's slow - down to the specific function and line number.

**The Problem:** Your traces show `Span: "process_context" - Duration: 2,580ms ⚠️ SLOW`, but you don't know why.

**The Solution:** APM reveals `chunk_overlap_filter()` at line 187 consuming 2.1s in O(n²) comparisons.

### Key Features
- Datadog APM initialization with OpenTelemetry bridge (no double instrumentation)
- Profiled RAG pipeline with custom instrumentation
- Memory leak detection using tracemalloc
- Production-safe configurations with <5% overhead
- Cost monitoring and safety checks

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your DD_API_KEY from datadoghq.com
```

### 3. Run Smoke Tests

```bash
python tests_smoke.py
```

Expected output: 7/7 tests passed (works without Datadog credentials)

### 4. Explore the Jupyter Notebook

```bash
jupyter notebook L2_M7_Application_Performance_Monitoring.ipynb
```

The notebook walks through:
- APM theory and architecture
- Initializing APM with OpenTelemetry bridge
- Profiling a RAG pipeline
- Memory leak detection and fixes
- Common failures and solutions
- Decision framework for choosing APM

### 5. Run FastAPI Application

**Without Datadog (works without keys):**
```bash
python app.py
# Or: uvicorn app:app --reload
```

**With Datadog APM (requires DD_API_KEY):**
```bash
ddtrace-run uvicorn app:app --host 0.0.0.0 --port 8000
```

### 6. Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Process query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are GDPR requirements?",
    "user_id": "test_user"
  }'

# Memory stats
curl http://localhost:8000/memory

# Prometheus metrics (if available)
curl http://localhost:8000/metrics
```

## How It Works

### Observability Stack
```
├── Logs (WHAT happened) ← Level 1 M2.3
├── Metrics (HOW MUCH) ← Level 1 M2.3
├── Traces (WHERE in pipeline) ← Level 2 M7.1
└── APM (WHY at code level) ← This Module
```

### Architecture

```
Your Python App
├── OpenTelemetry (Traces from M7.1)
│   └── Span: "process_query" - 2.5s
│
└── Datadog APM (Profiling)
    └── WITHIN that span:
        ├── Function: embedding_model() - 200ms
        ├── Function: chunk_filter() - 2.1s ⚠️
        │   └── Line 187: nested loop - 1.8s ⚠️⚠️
        └── Function: format_response() - 200ms
```

### APM Process
1. APM agent samples your Python process (100 samples/second)
2. Each sample captures the call stack (which functions are executing)
3. Statistical profile: "85% of time is in chunk_filter()"
4. APM correlates this with your OpenTelemetry traces

### Production-Safe Defaults
- **1% profiling capture** - <1% overhead
- **10% trace sampling** - Balances cost ($5/1M spans) with visibility
- **5% max CPU overhead** - Safety limit
- **50% DB query sampling** - Good signal without excessive cost

## Common Failures & Fixes

### Failure 1: APM Overhead Crushing Performance (5-15% slowdown)

**Symptoms:**
- P95 latency increases from 800ms to 1.2s (50% slowdown)
- CPU usage spikes to 95%
- APM warnings: "High profiling overhead: 15.2% CPU"

**Root Cause:** Aggressive profiling configuration
```python
DD_PROFILING_CAPTURE_PCT=10  # Too high!
DD_TRACE_SAMPLE_RATE=1.0     # 100% sampling!
```

**Fix:**
```bash
DD_PROFILING_CAPTURE_PCT=1   # Production-safe
DD_TRACE_SAMPLE_RATE=0.1     # 10% sampling
DD_PROFILING_MAX_TIME_USAGE_PCT=5
```

### Failure 2: Memory Profiler Crashes Production

**Symptoms:** MemoryError, OOM killed, application hangs

**Root Cause:** Using `@profile` decorator from memory-profiler in production (creates 20GB overhead)

**Fix:** NEVER use `@profile` in production. Use `tracemalloc` instead (built into Python, production-safe)

### Failure 3: Memory Leak Detection Challenges

**Symptoms:**
- Memory grows from 100MB to 8GB over 24 hours
- APM shows steady growth but doesn't pinpoint leak

**Root Cause:** APM shows ALLOCATION but not RETENTION

**Fix:**
- Use `objgraph.growth()` to find retained objects
- Implement LRU cache with eviction:
```python
cache = OrderedDict()
cache[key] = value
if len(cache) > max_size:
    cache.popitem(last=False)  # Remove oldest
```

### Failure 4: APM Cost Explosion ($500+ bill)

**Symptoms:** Bill shows $460/month vs expected $51/month

**Root Cause:** Developer set `DD_TRACE_SAMPLE_RATE=1.0` for debugging, forgot to revert

**Fix:**
- Add config validation that fails deployment with unsafe settings
- Monitor costs daily using Datadog usage API
- Set alerts for unexpected usage spikes

## Decision Card

### ✅ BENEFIT
Deep code-level profiling reveals bottlenecks down to specific function calls and line numbers. Reduces debugging time from hours to minutes by showing CPU hotspots, memory leaks, and slow queries with flame graphs. Correlates performance issues with traces from M7.1.

### ❌ LIMITATION
Adds 2-5% CPU overhead in production even with conservative sampling (1% profiling, 10% trace sampling). Cost scales rapidly: $51/month minimum, rising to $300+/month at 100K requests/hour due to per-span analysis fees ($5 per 1M spans). Memory profiling shows allocations but struggles to detect slow retention-based leaks.

### 💰 COST
- **Time to implement:** 2-4 hours for initial setup, 1-2 days for production tuning
- **Monthly cost:** $51-100 for small deployments (1-3 hosts), $300-800 for medium scale (10-15 hosts, 10M spans/day)
- **Complexity:** 300+ lines of APM config code, requires understanding of profiling overhead vs visibility trade-offs

### 🤔 USE WHEN
Traffic exceeds 1K requests/hour with known performance problems (P95 >3s), budget allows $50-200/month for APM, team of 3+ engineers who will actively monitor dashboards, and no compliance restrictions on sending telemetry to third-party services like Datadog.

### 🚫 AVOID WHEN
Traffic below 1K requests/hour (insufficient data for profiling patterns - use py-spy instead), budget under $100/month total (APM would be 50%+ of costs - use open-source Grafana Tempo), processing sensitive data requiring full data sovereignty (use self-hosted APM), or no known performance issues yet (premature optimization - wait until P95 crosses 3s).

## Alternative Solutions

### Option 1: Open-Source APM (Grafana Tempo + Pyroscope)
- **Cost:** $20-40/month (self-hosted VM costs)
- **Pros:** Full data sovereignty, cost-effective at scale
- **Cons:** 2-3 hours setup, requires DevOps expertise
- **When:** Team size 5+, budget <$100/month, data sovereignty required

### Option 2: Cloud Provider APM (AWS X-Ray, GCP Cloud Profiler)
- **Cost:** $15-50/month
- **Pros:** Integrated with cloud platform, minimal setup
- **Cons:** Vendor lock-in, basic profiling only
- **When:** Already on AWS/GCP, budget-conscious, simple needs

### Option 3: Manual Profiling with py-spy
- **Cost:** $0
- **Pros:** Zero overhead when not profiling, 5-minute setup
- **Cons:** Manual process, no production correlation
- **When:** Traffic <1K req/hour, one-off debugging

## Troubleshooting

### APM Not Initializing

**Check:**
```bash
python -c "from config import apm_config; print(apm_config.is_enabled())"
```

**If False:** Add `DD_API_KEY` to `.env`

### High CPU Overhead

**Check current settings:**
```bash
python -c "from config import apm_config; print(f'Profiling: {apm_config.DD_PROFILING_CAPTURE_PCT}%')"
```

**Reduce if >1%:**
```bash
export DD_PROFILING_CAPTURE_PCT=1
export DD_TRACE_SAMPLE_RATE=0.1
```

### No Data in Datadog UI

**Verify:**
1. `DD_API_KEY` is set correctly
2. `DD_SITE` matches your region (datadoghq.com or datadoghq.eu)
3. Application is running with `ddtrace-run` wrapper
4. Wait 2-3 minutes for first data to appear

### Import Errors

**If `ddtrace` not found:**
```bash
pip install ddtrace
```

**If still failing:**
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org ddtrace
```

## File Structure

```
.
├── l2_m7_application_performance_monitoring.py  # Core module
├── app.py                                        # FastAPI entrypoint
├── config.py                                     # APM configuration
├── requirements.txt                              # Dependencies
├── .env.example                                  # Environment template
├── example_data.json                             # Sample data
├── tests_smoke.py                                # Smoke tests
├── L2_M7_Application_Performance_Monitoring.ipynb # Tutorial notebook
└── README.md                                     # This file
```

## Production Deployment Checklist

Before deploying to production:

- [ ] Sample rate ≤10% (`DD_TRACE_SAMPLE_RATE=0.1`)
- [ ] Profiling capture ≤1% (`DD_PROFILING_CAPTURE_PCT=1`)
- [ ] Max CPU overhead limit set to 5%
- [ ] Cost alerting configured
- [ ] Excluded paths configured (`/health`, `/metrics`)
- [ ] Load tested with APM enabled
- [ ] Rollback plan ready

### Deployment Command

```bash
# Production deployment with APM
ddtrace-run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Emergency Rollback

```bash
# Disable APM without restart
export DD_PROFILING_ENABLED=false
export DD_TRACE_SAMPLE_RATE=0.0

# Or restart without ddtrace-run wrapper
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Cost Estimates

| Scale | Hosts | Requests/Day | Spans/Day | Datadog Cost | Open-Source |
|-------|-------|--------------|-----------|--------------|-------------|
| Small | 1 | 24,000 | 100K | $51/mo | $20/mo |
| Medium | 3-5 | 240,000 | 1M | $120/mo | $40/mo |
| Large | 15+ | 2,400,000 | 10M | $800/mo | $100/mo |

## Next Steps

1. **Sign up for Datadog:** Free 14-day trial at datadoghq.com
2. **Add credentials:** Update `.env` with your `DD_API_KEY`
3. **Run the notebook:** Complete all sections to understand APM
4. **Deploy to staging:** Test with `ddtrace-run` wrapper
5. **Monitor costs:** Set up usage alerts in Datadog
6. **Tune configuration:** Adjust sampling based on traffic patterns

## Related Modules

- **Level 1 M2.3:** Production Monitoring Dashboard (Prometheus/Grafana)
- **Level 2 M7.1:** Distributed Tracing with OpenTelemetry
- **Next:** Module 7.3 - Cost Optimization for Observability

## Resources

- [Datadog APM Documentation](https://docs.datadoghq.com/tracing/)
- [ddtrace Python Library](https://ddtrace.readthedocs.io/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [py-spy Profiler](https://github.com/benfred/py-spy)
- [Grafana Tempo (Open-Source)](https://grafana.com/oss/tempo/)

## License

Educational use only - Part of Level 2 Observability Training
