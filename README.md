# Module 6.4: Compliance & Audit Logging

Production-ready audit logging system with tamper-proof trails, GDPR automation, and retention policies for RAG applications.

## Overview

This module implements comprehensive compliance audit logging using the ELK stack (Elasticsearch, Logstash, Kibana) with:

- **Tamper-proof audit trails** using SHA-256 hash chaining (blockchain-style)
- **GDPR automation** (Right to Portability, Right to Erasure, consent tracking)
- **Automated retention policies** based on data classification
- **Chain integrity verification** to detect tampering
- **Fallback storage** for high availability

### Real-World Impact

- Reduces GDPR audit work from **40 hours to <1 hour** (95%+ automation)
- Avoids compliance fines (GDPR fines up to 4% of annual revenue)
- Meets SOC 2, ISO 27001, HIPAA requirements

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Elasticsearch credentials
```

### 3. Run the API

```bash
python app.py
```

Visit http://localhost:8000/docs for interactive API documentation.

### 4. Explore the Notebook

```bash
jupyter notebook L2_M6_Compliance_Audit_Logging.ipynb
```

### 5. Run Tests

```bash
pytest tests_smoke.py -v
```

## How It Works

### Architecture Diagram

```
┌─────────────┐
│  User Action│
└──────┬──────┘
       │
       v
┌──────────────────┐
│ FastAPI Endpoint │
│  (with RBAC)     │
└──────┬───────────┘
       │
       v
┌──────────────────┐       ┌─────────────────┐
│  Audit Event     │       │  Elasticsearch  │
│  Generation      │──────>│  (Centralized   │
│  (WHO/WHAT/WHEN) │       │   Storage)      │
└──────┬───────────┘       └─────────────────┘
       │                            │
       v                            v
┌──────────────────┐       ┌─────────────────┐
│  Hash Chaining   │       │     Kibana      │
│  (Tamper-Proof)  │       │   (Dashboard)   │
└──────────────────┘       └─────────────────┘
```

### Key Components

**1. Audit Event Schema** (`AuditEvent`)
- Captures WHO (user, role, IP), WHAT (action, resource), WHEN (timestamp), WHERE (service, endpoint), OUTCOME (success/failure)
- 14 event types: login, document access, PII detection, GDPR requests, etc.

**2. Tamper-Proof Storage** (`AuditStorage`)
- SHA-256 hash of each event
- Blockchain-style chaining (each event links to previous via hash)
- Elasticsearch time-series indices (monthly rollover)
- Fallback to local file if Elasticsearch unavailable

**3. GDPR Compliance** (`GDPRCompliance`)
- **Right to Portability:** Export all user audit data
- **Right to Erasure:** Delete user data after retention period
- **Consent Tracking:** Log consent given/withdrawn events

**4. Retention Policies** (`RetentionPolicy`)
- **Confidential:** 7 years (2,555 days)
- **Internal:** 3 years (1,095 days)
- **Public:** 1 year (365 days)
- **Security-critical:** 10 years (3,650 days)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/audit/event` | POST | Create audit event |
| `/audit/verify` | GET | Verify chain integrity |
| `/gdpr/export` | POST | Export user data (Article 20) |
| `/gdpr/delete` | POST | Delete user data (Article 17) |
| `/gdpr/consent/{user_id}` | POST | Track consent |
| `/retention/enforce` | POST | Enforce retention policy |

## Common Failures & Fixes

### Failure 1: Incomplete Audit Trail
**Problem:** Missing critical events (permission denials, PII access)
**Impact:** Non-compliant during audit
**Fix:** Use audit checklist covering all 14 event types

### Failure 2: No Tamper-Proof Verification
**Problem:** No hash chaining, logs can be modified
**Impact:** Cannot prove log integrity
**Fix:** Enable hash chaining (`AUDIT_ENABLE_HASH_CHAIN=true`) + run daily verification

### Failure 3: Retention Policy Gaps
**Problem:** Logs deleted too early or kept forever
**Impact:** Compliance violations
**Fix:** Automate retention enforcement via cron job

### Failure 4: Performance Degradation
**Problem:** Sync audit logging blocks requests
**Impact:** >100ms latency increase
**Fix:** Use async logging + batch inserts (already implemented)

### Failure 5: Elasticsearch Downtime = No Auditing
**Problem:** When ES down, audit events lost
**Impact:** Compliance gaps
**Fix:** Fallback to local file storage (already implemented)

## Decision Card

### ✅ USE WHEN
- You handle **regulated data** (PII, healthcare, financial)
- Need **SOC 2 or ISO 27001** certification
- Have **1,000-50,000 queries/day**
- Have **DevOps capacity** to maintain Elasticsearch
- Audit requirements exceed simple access logs

### 🚫 AVOID WHEN
- **MVP with no regulated data** → Use simple JSON logging
- **Scale exceeds 50K queries/day** → Use AWS CloudTrail
- **100% on cloud services** → Use cloud provider native logs
- **DevOps budget <$100/month** → Use Vanta or managed platform

### 💰 COST
- **Initial:** 8-12 hours setup
- **Monthly:** $50-200 (small-medium), up to $1,000+ (large scale)
- **Storage:** $23/month per TB
- **Maintenance:** 2-4 hours/month
- **Total first year:** ~$600-2,400 + 40-60 hours engineering

### ❌ LIMITATIONS
- Adds 3 infrastructure components (ELK stack)
- Storage grows at 1GB/10K events
- Requires Elasticsearch expertise at scale
- Cannot prevent tampering by root user without immutable backup

## Troubleshooting

### Elasticsearch Connection Failed

```bash
# Check Elasticsearch is running
curl http://localhost:9200

# If using Docker:
docker ps | grep elasticsearch

# View ES logs:
docker logs elasticsearch
```

**Solution:** Ensure `ELASTICSEARCH_HOST` and `ELASTICSEARCH_PORT` are correct in `.env`. If Elasticsearch is unavailable, the system will use fallback file storage.

### Events Not Appearing in Elasticsearch

```bash
# Check indices exist
curl http://localhost:9200/_cat/indices?v

# Query recent events
curl http://localhost:9200/audit-logs-*/_search?size=5
```

**Solution:** Verify index template was created. Check `app.py` logs for errors.

### Chain Integrity Verification Failed

**Cause:** Events were modified or deleted after creation.

**Solution:**
1. Investigate which event failed verification
2. Check server access logs for unauthorized modifications
3. Restore from immutable backup (if configured)
4. Implement S3 Object Lock for future prevention

### High Storage Costs

**Cause:** Too many events or long retention periods.

**Solutions:**
- Implement sampling (log 10% of routine events, 100% of critical)
- Reduce retention periods (if compliance allows)
- Use tiered storage (hot/warm/cold in Elasticsearch ILM)
- Switch to AWS CloudTrail at >50K queries/day

## Files

| File | Description |
|------|-------------|
| `l2_m6_compliance_audit_logging.py` | Core module with all functionality |
| `app.py` | FastAPI application entrypoint |
| `config.py` | Configuration management |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `example_data.json` | Sample audit events |
| `tests_smoke.py` | Basic smoke tests |
| `L2_M6_Compliance_Audit_Logging.ipynb` | Interactive tutorial notebook |

## Next Steps

After completing this module:

1. **Module 7.1: Distributed Tracing** - Track requests across microservices with OpenTelemetry
2. **Module 7.2: Application Performance Monitoring** - Monitor query latency, cache hit rates
3. **Module 7.3: Custom Metrics & Dashboards** - Build observability dashboards

## Resources

- **Elasticsearch Guide:** https://www.elastic.co/guide/
- **GDPR Compliance:** https://gdpr.eu/
- **SOC 2 Requirements:** https://www.aicpa.org/soc2
- **HIPAA Security Rule:** https://www.hhs.gov/hipaa/

## License

Educational use only. Not production-ready without proper security review.

---

**Module:** 6.4
**Level:** 2
**Prerequisites:** M6.1 (PII Detection), M6.2 (Secrets Management), M6.3 (RBAC)
**Duration:** 32 minutes
**Difficulty:** Intermediate
