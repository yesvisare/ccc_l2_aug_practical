# Module 7.3: Custom Business Metrics for RAG Systems

**Level 2 - Distributed Tracing & Advanced Observability**

---

## Purpose
Track business‑level KPIs for RAG (feature adoption, satisfaction, revenue attribution) and connect them to technical telemetry.

## Concepts Covered
Cohorts, feature usage, satisfaction & hallucination metrics, KPI aggregation, Prometheus export, offline‑first testability.

## After Completing
You can instrument/compute business KPIs for RAG, expose them via API/Prometheus, and validate them with smoke tests.

## Context in Track
L2 → Observability & Tracing; this module complements technical metrics with business value signals before L3 scaling.

---

## Overview

This module teaches how to track RAG-specific **business metrics** beyond technical monitoring, bridging the gap between infrastructure observability and executive decision-making.

### The Core Problem

Technical metrics (latency, errors, uptime) tell you **"Is the system working?"**
Business metrics (satisfaction, feature adoption, revenue attribution) tell you **"Is it creating value?"**

**Key Insight**: Technical metrics tell you HOW FAST things run, not HOW VALUABLE they are to users or the business.

### What You'll Learn

- Track RAG quality metrics (accuracy, satisfaction, hallucination rate)
- Implement user cohort analysis (FREE, PAID, ENTERPRISE, etc.)
- Monitor feature usage and adoption
- Calculate executive KPIs from raw metrics
- Build Grafana dashboards executives understand

---

## Quickstart

### Prerequisites

- Python 3.11+
- Completed Level 1 M2.3 (Prometheus/Grafana)
- Module 7.1 (Distributed Tracing)
- Module 7.2 (APM Integration)

### Installation

```bash
# Clone and enter directory
cd ccc_l2_aug_practical

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | Runtime environment (development/production) |
| `DEBUG` | Enable debug mode (true/false) |
| `LOG_LEVEL` | Logging level (INFO/DEBUG/ERROR) |
| `PROMETHEUS_ENABLED` | Enable Prometheus metrics export |
| `PROMETHEUS_PORT` | Port for Prometheus metrics endpoint |
| `PROMETHEUS_PATH` | Path for metrics endpoint |
| `PROMETHEUS_PUSH_GATEWAY_URL` | Optional Prometheus push gateway |
| `REDIS_ENABLED` | Enable Redis for fast cohort lookups |
| `REDIS_HOST` | Redis server hostname |
| `REDIS_PORT` | Redis server port |
| `REDIS_DB` | Redis database number |
| `REDIS_PASSWORD` | Redis authentication password |
| `REDIS_TTL_SECONDS` | Cache TTL for cohort data |
| `CLICKHOUSE_ENABLED` | Enable ClickHouse for analytics (>100K queries/month) |
| `CLICKHOUSE_HOST` | ClickHouse server hostname |
| `CLICKHOUSE_PORT` | ClickHouse server port |
| `CLICKHOUSE_DATABASE` | ClickHouse database name |
| `CLICKHOUSE_USER` | ClickHouse username |
| `CLICKHOUSE_PASSWORD` | ClickHouse password |
| `COHORT_LOOKUP_MAX_MS` | Max time for cohort lookup (must be <10ms) |
| `MAX_LABEL_CARDINALITY` | Max unique label values (prevent cardinality explosion) |
| `HALLUCINATION_ALERT_THRESHOLD` | Alert threshold for hallucination rate (%) |
| `POWER_USER_QUERY_THRESHOLD` | Min queries/month to classify as power user |
| `AVG_QUERY_COST_DOLLARS` | Average cost per query in USD |
| `API_HOST` | FastAPI server host |
| `API_PORT` | FastAPI server port |
| `API_RELOAD` | Enable auto-reload for development |

### Running the Application

**Windows (recommended):**
```powershell
# Run API
powershell -c "$env:PYTHONPATH='$PWD'; uvicorn app:app --reload"

# Run tests
powershell -c "$env:PYTHONPATH='$PWD'; pytest -q"

# Or use helper scripts
.\scripts\run_api.ps1
.\scripts\run_tests.ps1
```

**Linux/Mac:**
```bash
# Run API
python app.py

# Run tests
pytest

# Start Jupyter notebook
jupyter notebook notebooks/L2_M7_Custom_Business_Metrics.ipynb
```

---

## How It Works

```
┌─────────────────┐
│  RAG Query      │
│  (user request) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Record Business Metrics            │
│  ┌───────────────────────────────┐  │
│  │ • Accuracy (4 categories)     │  │
│  │ • Satisfaction (1-5 scale)    │  │
│  │ • Confidence (0.0-1.0)        │  │
│  │ • Feature used                │  │
│  │ • User cohort (6 types)       │  │
│  └───────────────────────────────┘  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Prometheus Metrics                 │
│  (bounded labels only!)             │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Aggregate into Executive KPIs      │
│  ┌───────────────────────────────┐  │
│  │ • Cost per user               │  │
│  │ • Satisfaction trend          │  │
│  │ • Feature adoption rates      │  │
│  │ • Cohort retention            │  │
│  │ • Hallucination rate          │  │
│  └───────────────────────────────┘  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Grafana Dashboard                  │
│  (executive-friendly visualizations)│
└─────────────────────────────────────┘
```

### Key Components

1. **Bounded Cohorts**: Use 6 fixed user segments (FREE, PAID, ENTERPRISE, NEW, POWER, AT_RISK) instead of unbounded user IDs
2. **Fast Lookup**: Cohort determination must be <10ms (use Redis cache or nightly precomputation)
3. **Prometheus Metrics**: Counter, Gauge, Histogram, Summary for different metric types
4. **KPI Aggregation**: Transform raw metrics into business-relevant measurements

---

## Common Failures & Fixes

### Failure 1: Cardinality Explosion 💥

**What happens**: Using unbounded labels (user_id, query_id) causes Prometheus storage to explode.

**Symptoms**:
- Prometheus storage growing rapidly (>10GB/day)
- Query timeouts in Grafana
- High memory usage

**Fix**:
```python
# ❌ BAD - Unbounded label
query_counter.labels(user_id="u12345").inc()

# ✓ GOOD - Bounded cohort
query_counter.labels(cohort="paid").inc()
```

**Prevention**:
```python
# Validate labels before use
is_valid = validate_metric_labels(labels)
```

---

### Failure 2: Dashboard Timeouts ⏱️

**What happens**: Complex queries over large datasets cause Grafana dashboards to timeout.

**Symptoms**:
- Dashboards loading for >30 seconds
- "Query timeout" errors
- High CPU on Prometheus

**Fix**:
- Use recording rules for frequently-computed queries
- Implement metric aggregation strategies
- Set appropriate retention policies:
  - Raw metrics: 15 days
  - Hourly aggregates: 60 days
  - Daily aggregates: 365 days

**Example recording rule**:
```yaml
groups:
  - name: business_metrics
    interval: 60s
    rules:
      - record: rag:satisfaction:avg_7d
        expr: avg_over_time(rag_user_satisfaction[7d])
```

---

### Failure 3: Inaccurate Cohorts 🎯

**What happens**: Wrong user segmentation logic leads to misleading metrics.

**Symptoms**:
- Power users classified as AT_RISK
- Enterprise users appearing in FREE cohort
- Cohort metrics don't match billing data

**Fix**:
```python
def get_user_cohort(user_id, user_metadata):
    # PRIORITY ORDER matters!

    # 1. Tier (highest priority)
    if tier == 'enterprise':
        return UserCohort.ENTERPRISE

    # 2. Activity patterns
    if days_since_last_query > 14:
        return UserCohort.AT_RISK

    # 3. Usage patterns
    if query_count > 100:
        return UserCohort.POWER

    # 4. Recency
    if days_since_signup <= 30:
        return UserCohort.NEW

    # 5. Default
    return UserCohort.FREE
```

**Prevention**:
- Document cohort definitions clearly
- Validate cohort logic against billing data
- Monitor cohort distribution over time

---

### Failure 4: Missing Metrics 📊

**What happens**: Blind spots around critical business signals.

**Symptoms**:
- Can't answer executive questions about user value
- Discover issues days/weeks later
- No data to support product decisions

**Fix**:
Implement comprehensive metric coverage:

```python
# Query accuracy
query_accuracy_counter.labels(accuracy=..., cohort=...).inc()

# User satisfaction
user_satisfaction_histogram.labels(cohort=..., feature=...).observe(rating)

# Hallucination monitoring
hallucination_rate_gauge.labels(cohort=...).set(rate)

# Model confidence
model_confidence_summary.labels(feature=...).observe(confidence)

# Feature usage
feature_usage_counter.labels(feature=..., cohort=...).inc()

# Cost tracking
cohort_cost_counter.labels(cohort=...).inc(cost)
```

---

### Failure 5: Calculation Errors 🧮

**What happens**: Incorrect aggregation logic in KPI formulas.

**Symptoms**:
- Cost per user is $0.01 when it should be $5.00
- Satisfaction trend shows "up" when it's declining
- Feature adoption percentages don't sum to 100%

**Fix**:
```python
# Validate calculations
def calculate_cost_per_user(total_cost, active_users):
    if active_users == 0:
        logger.warning("Cannot calculate CPU: no active users")
        return None  # Don't return 0 or infinity

    return total_cost / active_users

# Test edge cases
assert calculate_cost_per_user(100, 0) is None
assert calculate_cost_per_user(100, 50) == 2.0
```

**Prevention**:
- Write unit tests for all KPI calculations
- Validate against known baseline values
- Monitor KPI anomalies with alerts

---

## Decision Card

### ✓ Use Prometheus + Grafana When:

- RAG system under **100K queries/month**
- Need quick business visibility without BI overhead
- Team already using Prometheus for technical metrics
- Analytics budget under **$100/month**
- Infrastructure team can manage Prometheus/Grafana

### ❌ Don't Use This Approach When:

- Under **100 users** without product-market fit → Use manual reports
- Need detailed **user journey/funnel analysis** → Use product analytics platforms
- Scaling beyond **100K queries/month** → Invest in ClickHouse or data warehouse
- Require **complex ad-hoc queries** → Use BI tools (Looker, Tableau)

### Alternative Solutions

| Solution | Best For | Cost | Trade-off |
|----------|----------|------|-----------|
| **Mixpanel/Amplitude** | User journey analysis, cohort experiments | $200-1000+/mo | More features, higher cost |
| **Looker/Tableau** | Complex queries, executive reporting | $300-2000+/mo | Superior analytics, needs data warehouse |
| **Manual Reports** | <100 users, early stage | Time only | Free but doesn't scale |
| **ClickHouse** | >100K queries/month | $50-200/mo | High performance, more ops overhead |

---

## Production Considerations

### Scaling Thresholds

- **Small** (<1K queries/month): Prometheus only, $20/month
- **Medium** (1K-10K queries/month): Prometheus + Redis cache, $35/month
- **Large** (10K-100K queries/month): Add recording rules, $50/month
- **Enterprise** (>100K queries/month): Add ClickHouse, $100-200/month

### Cost Breakdown (Monthly)

```
Prometheus (self-hosted):    $20
Grafana (open source):       $0
Redis (optional caching):    $15
ClickHouse (optional):       $50
Cloud hosting:               $20-50
─────────────────────────────
Total: $35-135/month
```

### Monitoring Requirements

Set up alerts for:

- **Metric ingestion rate**: Should be steady, not spiking
- **Dashboard query performance**: <5 seconds load time
- **Hallucination rate**: Alert if >5% (configurable threshold)
- **Cohort lookup latency**: Alert if >10ms average
- **Prometheus storage**: Alert if >80% capacity

### Deployment Checklist

Before going to production:

- [ ] Configure Redis for fast cohort lookups
- [ ] Set Prometheus retention policies (15d/60d/365d)
- [ ] Create Grafana dashboards for executives
- [ ] Set up hallucination rate alerts
- [ ] Test cardinality limits on metric labels
- [ ] Document cohort definitions for stakeholders
- [ ] Validate KPI calculations against baseline data
- [ ] Test dashboard performance with production load
- [ ] Set up backup strategy for Prometheus data
- [ ] Configure Grafana access controls

---

## API Reference

### REST Endpoints

Start the API server:
```bash
python app.py
# Server runs on http://localhost:8080
```

**Health Check**
```bash
GET /health
```

**Record Query Metrics**
```bash
POST /metrics/query
Content-Type: application/json

{
  "query_id": "q123",
  "user_id": "u456",
  "user_metadata": {
    "tier": "paid",
    "days_since_signup": 60,
    "query_count": 120,
    "days_since_last_query": 1
  },
  "accuracy": "accurate",
  "satisfaction": 5,
  "confidence": 0.92,
  "feature": "simple_qa",
  "latency_ms": 234.5
}
```

**Update Hallucination Rate**
```bash
POST /metrics/hallucination_rate
Content-Type: application/json

{
  "cohort": "free",
  "total_queries": 1000,
  "hallucinated_queries": 15
}
```

**Get Executive Summary**
```bash
POST /kpi/summary
Content-Type: application/json

{
  "time_period": "last_7_days",
  "cohorts": ["paid", "enterprise"]
}
```

**Prometheus Metrics**
```bash
GET /metrics
```

---

## Troubleshooting

### Issue: Prometheus storage growing rapidly

**Diagnosis**:
```bash
# Check metric cardinality
curl http://localhost:9090/api/v1/label/__name__/values | jq '.data | length'

# Check series count
curl http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName'
```

**Solution**: Review metric labels, ensure using bounded cohorts not user IDs.

---

### Issue: Cohort lookup too slow (>10ms)

**Diagnosis**:
```python
import time

start = time.time()
cohort = get_user_cohort(user_id, metadata)
elapsed_ms = (time.time() - start) * 1000

if elapsed_ms > 10:
    print(f"WARNING: Lookup took {elapsed_ms:.2f}ms")
```

**Solution**: Implement Redis caching or nightly precomputation.

---

### Issue: Grafana dashboard timeouts

**Diagnosis**: Check Prometheus query logs for slow queries.

**Solutions**:
1. Add recording rules for complex queries
2. Reduce time range (7d instead of 30d)
3. Use downsampled data (hourly instead of raw)
4. Optimize PromQL queries

---

### Issue: Metrics not appearing in Grafana

**Checklist**:
1. Check Prometheus is scraping: `curl http://localhost:9090/metrics`
2. Verify metric names match: `curl http://localhost:9090/api/v1/label/__name__/values`
3. Check time range in Grafana (metrics may be recent)
4. Verify Prometheus data source configured correctly

---

## Next Steps

### Continue Learning

- **Module 7.4**: Log Aggregation with ELK Stack
- **Module 7.5**: Real-time Alerting & Incident Response

### Practathon Challenges

**Easy (60 min)**: Basic metric implementation
- Implement all RAG quality metrics
- Set up cohort determination
- Create simple Grafana dashboard

**Medium (90-120 min)**: Multi-cohort analysis
- Add Redis caching for cohorts
- Implement recording rules
- Build executive KPI dashboard

**Hard (4-5 hours)**: Complete KPI system with alerting
- Full production deployment
- ClickHouse integration for advanced analytics
- Alert system for business KPI thresholds
- Executive reporting automation

---

## Resources

### Documentation

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [PromQL Query Examples](https://prometheus.io/docs/prometheus/latest/querying/basics/)

### Example Queries

**Average satisfaction by cohort (7 days)**:
```promql
avg_over_time(rag_user_satisfaction{cohort="paid"}[7d])
```

**Hallucination rate trend**:
```promql
rate(rag_query_accuracy_total{accuracy="hallucinated"}[1h])
/
rate(rag_query_accuracy_total[1h])
* 100
```

**Cost per user by cohort**:
```promql
rate(rag_cohort_cost_dollars[1d])
/
rag_active_users
```

---

## Support & Contributing

### Getting Help

- Review the Jupyter notebook: `L2_M7_Custom_Business_Metrics.ipynb`
- Run smoke tests: `pytest tests_smoke.py -v`
- Check API docs: `http://localhost:8080/docs` (when server running)

### Common Questions

**Q: Why not use user IDs as labels?**
A: Unbounded labels cause Prometheus cardinality explosion. Use bounded cohorts instead.

**Q: How do I add a new cohort?**
A: Add to `UserCohort` enum and update `get_user_cohort()` logic. Keep total cohorts <10.

**Q: Can I track individual user behavior?**
A: Not with Prometheus. Use product analytics platforms (Mixpanel, Amplitude) for user-level analysis.

**Q: What if I need >100K queries/month?**
A: Add ClickHouse for raw event storage, use Prometheus for aggregated metrics only.

---

## License

Educational use for Level 2 Observability Course.

---

**Key Insight**: Technical metrics tell you HOW FAST things run, not HOW VALUABLE they are to users or the business. This module bridges that gap.
