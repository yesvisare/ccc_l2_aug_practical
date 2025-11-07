# Module 7.4: Intelligent Alerting

Reduce false positives by 80-90% through statistical anomaly detection, alert aggregation, and automated remediation.

## Overview

Traditional threshold-based alerts (e.g., "alert if latency > 2s") create alert fatigue with 90% false positive rates. This module implements intelligent alerting that:

- **Detects anomalies** using Prophet time-series analysis (3-sigma deviation)
- **Aggregates alerts** by service and time window (10 alerts → 1 incident)
- **Integrates PagerDuty** for automated on-call escalation
- **Automates remediation** with runbooks for common failure patterns

**Key Insight:** Statistical models distinguish transient spikes from genuine degradation by analyzing historical patterns, not absolute thresholds.

## Quickstart

### 1. Installation

```bash
# Clone and navigate to directory
cd ccc_l2_aug_practical

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials (optional for demo)
# PROMETHEUS_URL=http://localhost:9090
# PAGERDUTY_API_KEY=your_key_here
```

### 3. Run Examples

```bash
# CLI examples (works without external services)
python l2_m7_intelligent_alerting.py

# Start FastAPI server
python app.py
# Access API docs: http://localhost:8000/docs

# Run tests
pytest tests_smoke.py -v

# Explore Jupyter notebook
jupyter notebook L2_M7_Intelligent_Alerting.ipynb
```

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Intelligent Alerting Flow                │
└─────────────────────────────────────────────────────────────┘

1. BASELINE COLLECTION (7+ days)
   ├─ Fetch metrics from Prometheus
   ├─ Resolution: 1-minute intervals (~10,080 points/week)
   └─ Store in time-series format (ds, y)

2. ANOMALY DETECTION
   ├─ Train Prophet model (daily/weekly seasonality)
   ├─ Predict expected range (99.7% confidence interval)
   ├─ Compare actual vs predicted
   └─ Flag if deviation > 3-sigma threshold
        ├─ Low:    3.0-4.0 sigma
        ├─ Medium: 4.0-5.0 sigma
        └─ High:   >5.0 sigma

3. ALERT AGGREGATION (5-minute window)
   ├─ Group alerts by: service + time_bucket
   ├─ Example: "high_latency" + "cache_miss" + "timeout_errors"
   └─ Create single incident with combined context

4. ON-CALL ESCALATION
   ├─ Create PagerDuty incident with severity
   ├─ Route to current on-call engineer
   └─ Deduplicate similar incidents

5. AUTO-REMEDIATION (optional)
   ├─ Match incident pattern to runbook
   ├─ Execute remediation (cache flush, restart, etc.)
   └─ Track success rate for feedback loop

Result: 20 noisy alerts → 1 actionable incident
```

## Common Failures & Fixes

### ❌ Failure #1: Alert Fatigue Despite Anomaly Detection
**Symptoms:** Still receiving 20+ alerts daily

**Root Cause:** Threshold too sensitive (σ < 2.5) or insufficient aggregation

**Resolution:**
```python
# Increase sigma threshold
detector = AnomalyDetector(std_threshold=4.0)

# Extend aggregation window
aggregator = AlertAggregator(window_seconds=600)  # 10 minutes
```

### ❌ Failure #2: Missed Critical Incidents
**Symptoms:** High-severity issues not triggering alerts

**Root Cause:** Over-tuned for false positive reduction

**Resolution:**
```python
# Monitor detection accuracy weekly
# Adjust threshold based on observed false negatives
# Consider hybrid model: anomaly detection + absolute threshold

if latency > 5.0:  # Hard limit for critical systems
    alert("Critical latency")
```

### ❌ Failure #3: False Anomalies from Legitimate Traffic
**Symptoms:** Black Friday sales trigger high-severity alerts

**Root Cause:** Model lacks context for planned events

**Resolution:**
```python
# Retrain model after known high-traffic periods
# Or: Add event calendar integration
# Or: Temporarily disable anomaly detection during events

if is_planned_event(timestamp):
    skip_anomaly_check()
```

### ❌ Failure #4: On-Call Rotation Gaps
**Symptoms:** Incidents created but no one responds

**Root Cause:** Incomplete PagerDuty escalation policies

**Resolution:**
- Audit on-call schedules weekly
- Configure backup escalation paths
- Test incident routing in staging environment

### ❌ Failure #5: Outdated Runbooks
**Symptoms:** Auto-remediation fails after infrastructure changes

**Root Cause:** Runbooks not updated with code deployments

**Resolution:**
```python
# Version runbooks with infrastructure code
# Add runbook tests to CI/CD pipeline
# Monthly dry-run tests in production

pytest tests/runbooks/ --prod-dry-run
```

## Decision Card

| Scenario | Recommendation |
|----------|----------------|
| **Mature system, 6+ months data** | ✅ Use intelligent alerting |
| **New service, <7 days data** | ⚠️ Use simple thresholds, migrate later |
| **Low alert volume (<10/week)** | ⚠️ Skip aggregation, overhead exceeds benefit |
| **Unpredictable traffic patterns** | ⚠️ Combine anomaly with manual thresholds |
| **Critical system (healthcare, finance)** | ⚠️ Add human review gate before auto-remediation |
| **Early-stage rapid infrastructure changes** | ❌ Wait for stable baseline period |

## When NOT to Use This Approach

1. **Services with <7 days data** - Insufficient baseline for Prophet training
2. **Low alert volume** - Aggregation complexity exceeds benefits
3. **Unpredictable traffic** - Seasonal products, event-driven systems confuse models
4. **Zero false-negative tolerance** - Healthcare, financial systems need absolute certainty
5. **Rapidly changing infrastructure** - Daily architecture changes invalidate historical patterns

## API Reference

### Train Model
```bash
POST /train
{
  "metric_name": "http_request_duration_seconds",
  "baseline_days": 7,
  "std_threshold": 3.0
}
```

### Detect Anomaly
```bash
POST /detect
{
  "timestamp": "2025-11-07T10:00:00Z",
  "value": 2.5
}
```

### Ingest Alert
```bash
POST /alerts/ingest
{
  "id": "alert_123",
  "metric": "latency",
  "service": "api-gateway",
  "timestamp": "2025-11-07T10:00:00Z",
  "severity": "high",
  "message": "High latency detected"
}
```

### Aggregate Alerts
```bash
POST /alerts/aggregate
```

### Execute Runbook
```bash
POST /runbook/execute
{
  "trigger": "cache_full",
  "parameters": {"percentage": 20}
}
```

## Architecture Considerations

### Data Volume
- **Training:** 7 days × 1-minute resolution = ~10,080 data points
- **Storage:** Manageable on standard hardware (<10 MB per metric)
- **Scaling:** Linear with number of monitored metrics

### Latency
- **Detection latency:** ~200-500ms per check
- **Evaluation window:** 5-minute intervals (not real-time streaming)
- **Aggregation delay:** Configurable (default 5 minutes)

### Cost (Monthly Estimates)
- **Prometheus storage:** $50-100
- **PagerDuty:** $0-500 (depends on incident volume)
- **Compute:** $20-50 (anomaly detection)
- **Total:** $70-650/month

## Troubleshooting

### Issue: "Insufficient training data" error
**Solution:** Ensure at least 7 days of historical metrics available

### Issue: Prometheus connection refused
**Solution:** Check PROMETHEUS_URL in .env, verify Prometheus is running

### Issue: PagerDuty incidents not created
**Solution:** Verify API key and service ID are correct, check logs for auth errors

### Issue: Model predicts poorly after deployment
**Solution:** Retrain model weekly or after significant infrastructure changes

### Issue: High memory usage during training
**Solution:** Reduce baseline_days or increase aggregation interval

## Production Deployment Checklist

- [ ] 7+ days of Prometheus baseline data collected
- [ ] Prophet model trained and validated on historical incidents
- [ ] PagerDuty integration tested with incident acknowledgment
- [ ] Auto-remediation runbooks tested in staging environment
- [ ] Alert aggregation rules tuned (<5% false positive rate)
- [ ] Escalation policies configured with backup on-call rotation
- [ ] Monitoring dashboards showing detection accuracy metrics
- [ ] Weekly alert quality reviews scheduled

## Next Steps

**Module 8:** Advanced observability topics (distributed tracing correlation, service mesh integration)

**Further Learning:**
- [Prophet Documentation](https://facebook.github.io/prophet/)
- [PagerDuty API Reference](https://developer.pagerduty.com/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)

## Key Takeaway

**Intelligent alerting trades complexity for signal clarity.** The 80-90% reduction in false positives justifies implementation overhead for systems generating >10 alerts daily with >20% false positive rates.

For systems with stable baselines and high alert volume, statistical anomaly detection transforms alert management from reactive firefighting to proactive incident response.
