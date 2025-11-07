# Module 7: Distributed Tracing & Advanced Observability
## Video M7.3: Custom Business Metrics (Enhanced with TVH Framework v2.0)
**Duration:** 35 minutes
**Audience:** Level 2 learners who completed Level 1 M2.3, M7.1, M7.2
**Prerequisites:** Prometheus/Grafana monitoring (M2.3), Distributed Tracing (M7.1), APM (M7.2)

---

## SECTION 1: INTRODUCTION & HOOK (2-3 minutes)

**[0:00-0:30] Hook - The Business Metrics Blindspot**

[SLIDE: Title - "Custom Business Metrics: Beyond Technical Monitoring"]

**NARRATION:**
"In Level 1 M2.3, you built technical monitoring with Prometheus and Grafana—tracking latency, cache hits, error rates. In M7.1 and M7.2, you added distributed tracing and APM. You can see EVERY technical detail of your RAG system.

But here's the problem: **Technical metrics don't answer business questions.**

Your CEO asks: 'Are users satisfied with the answers?' You show them P95 latency. They ask: 'Which features drive retention?' You show them cache hit rates. They ask: 'What's our cost per active user?' You show them... total Pinecone costs.

**None of these answer the actual business questions.**

You're tracking what's easy to measure (API calls, latency, errors) but missing what matters to the business:
- Query satisfaction scores
- Feature adoption rates  
- Cost per user cohort
- Answer accuracy drift over time
- Revenue-generating vs. support queries

In production, executives don't care that P95 is 234ms. They care that user satisfaction dropped from 4.2 to 3.8 this week and retention is down 12%.

How do you track RAG-specific business metrics that executives can actually use for decisions?

Today, we're building that."

**[0:30-1:00] What You'll Learn**

[SLIDE: Learning Objectives]

"By the end of this video, you'll be able to:
- Track RAG-specific quality metrics (accuracy drift, user satisfaction) as custom Prometheus metrics
- Implement cohort analysis to understand user segments and behavior patterns
- Monitor feature usage to identify what's actually being used vs. built
- Build executive KPI dashboards that translate technical metrics into business value
- **Important:** When product analytics platforms are better than custom metrics and when simple reports beat dashboards"

**[1:00-2:30] Context & Prerequisites**

[SLIDE: Prerequisites Check]

"Before we dive in, let's verify you have the foundation:

**From Level 1 M2.3 (Production Monitoring):**
- ✅ Prometheus server running and scraping metrics
- ✅ Grafana connected with basic dashboards (latency, errors, cache hits)
- ✅ prometheus_client library instrumenting your FastAPI app

**From M7.1 (Distributed Tracing):**
- ✅ OpenTelemetry capturing request traces
- ✅ Jaeger showing trace spans

**From M7.2 (APM):**
- ✅ Datadog or New Relic profiling performance
- ✅ Technical bottlenecks identified

**If you're missing any of these, pause here and complete those modules first.**

Today's focus: Adding the business intelligence layer ON TOP of your existing technical monitoring. We're not replacing Prometheus—we're extending it to answer business questions that technical metrics can't."

---

## SECTION 2: PREREQUISITES & SETUP (2-3 minutes)

**[2:30-3:30] Starting Point Verification**

[SLIDE: "Where We're Starting From"]

**NARRATION:**
"Let's confirm our starting point. Your Level 2 system currently has:

- **Technical monitoring (M2.3):** Latency, errors, cache hits, token usage
- **Distributed tracing (M7.1):** Request flow visualization through services
- **APM (M7.2):** Performance profiling, bottleneck identification
- **What's missing:** Business context—satisfaction, cohorts, revenue impact

**The gap we're filling:** Your executives can't make decisions from technical dashboards.

Example showing current limitation:
```python
# Current approach from M2.3
from prometheus_client import Counter, Histogram

# You track TECHNICAL metrics
query_latency = Histogram('rag_query_latency_seconds', 'Query latency')
query_counter = Counter('rag_queries_total', 'Total queries', ['status'])

# But NOT business metrics:
# - Was the user satisfied with the answer?
# - What feature did they use (summarization vs. Q&A)?
# - What's their cohort (free vs. paid, new vs. power user)?
# - Did this query contribute to revenue or just support?
```

Problem: These technical metrics tell you HOW FAST things run, not HOW VALUABLE they are to users or the business.

By the end of today, you'll track:
- **Quality metrics:** Accuracy, hallucination rate, user satisfaction
- **Cohort metrics:** Free vs. paid behavior, new vs. retained users
- **Feature metrics:** Which RAG features drive value
- **Revenue metrics:** Cost and value per user segment

All queryable in Prometheus, visualized in Grafana, and actionable for executives."

**[3:30-5:00] New Dependencies**

[SCREEN: Terminal window]

**NARRATION:**
"We'll be adding ClickHouse for advanced analytics (optional but recommended for cohort analysis). Let's install:

```bash
# Core dependencies (required)
pip install prometheus-client --break-system-packages

# Optional but recommended for advanced cohort analysis
pip install clickhouse-driver asyncio-mqtt --break-system-packages

# For API instrumentation
pip install functools dataclasses --break-system-packages
```

**Quick verification:**
```python
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram, Info
print(prometheus_client.__version__)  # Should be 0.19.0 or higher

# Test ClickHouse connection (if using)
from clickhouse_driver import Client
client = Client('localhost')
print(client.execute('SELECT version()'))
```

**If installation fails:**
- **ClickHouse not starting:** Check port 9000 isn't in use
- **Import errors:** Ensure prometheus_client matches your Python version (3.8+)

**Important decision:** ClickHouse is OPTIONAL. Use it if:
- You need complex cohort analysis (>1M queries/month)
- You want to join metrics with external data (CRM, billing)
- You need SQL-like queries on metrics

Skip ClickHouse if:
- <10K queries/month (Prometheus + Grafana is enough)
- Simple cohort definitions (use Prometheus labels)
- No SQL requirement (Grafana visualizations sufficient)

For this video, I'll show BOTH approaches—pure Prometheus (simple) and Prometheus + ClickHouse (advanced). Choose based on your scale."

---

## SECTION 3: THEORY FOUNDATION (3-5 minutes)

**[5:00-8:30] Understanding Business Metrics vs. Technical Metrics**

[SLIDE: "Business Metrics Explained"]

**NARRATION:**
"Before we code, let's understand the conceptual difference between technical and business metrics.

**Technical metrics** answer: 'Is the system working?'
- Latency, error rates, throughput
- Infrastructure health (CPU, memory, disk)
- API availability and uptime

**Business metrics** answer: 'Is the system creating value?'
- User satisfaction with answers
- Feature adoption and engagement
- Cost efficiency per user segment
- Revenue attribution (which queries drive value?)

Think of it like a restaurant:
- **Technical metrics:** Kitchen temperature, prep time, ingredient inventory
- **Business metrics:** Customer satisfaction scores, popular menu items, revenue per table, food cost percentage

Both matter, but you can't run a business on kitchen temperature alone.

**How custom business metrics work:**

[DIAGRAM: Flow showing data path]
```
User Query â†' RAG System â†' Technical Metrics (latency, tokens)
             â†"
          Add context: user cohort, feature used, satisfaction
             â†"
      Custom Business Metric â†' Prometheus â†' Grafana Dashboard
```

**Step 1:** User interacts with RAG (query, rating, feature usage)
**Step 2:** You capture not just WHAT happened (query executed) but WHY and WHO (user intent, cohort, outcome)
**Step 3:** Custom Prometheus metrics expose this business context
**Step 4:** Grafana dashboards aggregate into KPIs executives understand

**Why this matters for production:**
- **Decision-making:** Executives can prioritize features based on usage, not intuition
- **Cost optimization:** Track cost per cohort, identify expensive user segments
- **Quality monitoring:** Detect accuracy drift before users complain (proactive)

**Common misconception:** 'Business metrics require complex BI tools like Looker or Tableau.'

**Reality:** For RAG systems at <100K queries/month, custom Prometheus metrics + Grafana give you 80% of BI platform value at 5% of the cost and complexity. You already HAVE the infrastructure—just add the right metrics."

---

## SECTION 4: HANDS-ON IMPLEMENTATION (20-25 minutes - 60-70% of video)

**[8:30-28:00] Step-by-Step Build**

[SCREEN: VS Code with code editor]

**NARRATION:**
"Let's build this step by step. We'll add custom business metrics to your existing M2.3 Prometheus setup, then create executive dashboards in Grafana.

### Step 1: Custom Prometheus Metrics for RAG Quality (5 minutes)

[SLIDE: Step 1 Overview]

First, we're creating metrics that track RAG-specific quality signals—accuracy, hallucination rate, user satisfaction.

```python
# business_metrics.py

from prometheus_client import Counter, Gauge, Histogram, Info
from enum import Enum
from typing import Optional

# ============================================================
# SECTION 1: RAG QUALITY METRICS
# ============================================================

class QueryOutcome(Enum):
    """Categorize query outcomes for quality tracking"""
    ACCURATE = "accurate"            # User confirmed answer correct
    PARTIAL = "partial"              # User got some value
    INACCURATE = "inaccurate"        # User marked as wrong
    HALLUCINATED = "hallucinated"    # AI made up facts not in docs
    NO_ANSWER = "no_answer"          # Couldn't find relevant info

# Track user-reported accuracy (binary feedback)
query_accuracy = Counter(
    'rag_query_accuracy_total',
    'User-reported query accuracy',
    ['outcome', 'model', 'user_cohort']  # ✅ Bounded labels
)

# Track satisfaction ratings (1-5 scale)
satisfaction_score = Histogram(
    'rag_satisfaction_score',
    'User satisfaction rating (1-5)',
    ['user_cohort', 'feature_used'],
    buckets=[1, 2, 3, 4, 5]  # Discrete buckets for ratings
)

# Track hallucination rate (gauge showing current rate)
hallucination_rate = Gauge(
    'rag_hallucination_rate',
    'Rolling 24h hallucination rate (%)',
    ['model']
)

# Track confidence scores from the model
answer_confidence = Histogram(
    'rag_answer_confidence',
    'Model confidence in answer (0-1)',
    ['user_cohort'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
)

# Example usage in your RAG query handler
def record_query_outcome(
    user_id: str,
    user_cohort: str,  # "free", "paid", "enterprise"
    model: str,
    outcome: QueryOutcome,
    satisfaction_rating: Optional[int] = None,
    confidence: float = 0.0
):
    """
    Record business metrics for a completed query.
    
    Call this AFTER the user provides feedback (thumbs up/down, rating).
    """
    # Increment accuracy counter
    query_accuracy.labels(
        outcome=outcome.value,
        model=model,
        user_cohort=user_cohort
    ).inc()
    
    # Record satisfaction if provided
    if satisfaction_rating:
        satisfaction_score.labels(
            user_cohort=user_cohort,
            feature_used="default"  # We'll add feature tracking next
        ).observe(satisfaction_rating)
    
    # Record confidence
    if confidence > 0:
        answer_confidence.labels(
            user_cohort=user_cohort
        ).observe(confidence)
    
    # Update hallucination rate (calculate from recent data)
    # This would typically be a background job, shown here for clarity
    if outcome == QueryOutcome.HALLUCINATED:
        # In production, you'd calculate this from a time-window query
        # For now, we're just demonstrating the metric
        hallucination_rate.labels(model=model).inc()
```

**Key design decisions:**
- **Labels are bounded:** user_cohort has 3 values (free/paid/enterprise), not unbounded user IDs
- **Outcome enum:** Forces consistency in outcome labeling
- **Separate recording function:** Decouples metric recording from RAG logic
- **Optional satisfaction:** Not every query gets rated—handle gracefully

**Why we did it this way:** We're tracking QUALITY (accuracy, satisfaction) not just PERFORMANCE (latency). These metrics require user feedback, so they lag behind the query by seconds to hours.

**Test this works:**
```python
# Test query outcome recording
record_query_outcome(
    user_id="user123",
    user_cohort="paid",
    model="gpt-4",
    outcome=QueryOutcome.ACCURATE,
    satisfaction_rating=5,
    confidence=0.92
)

print("✅ Metrics recorded. Check localhost:8000/metrics")
```

### Step 2: Cohort Analysis Metrics (5 minutes)

[SLIDE: Step 2 Overview]

Now we track USER COHORTS—groups of users with similar behavior or characteristics.

```python
# business_metrics.py (continued)

# ============================================================
# SECTION 2: COHORT ANALYSIS METRICS
# ============================================================

class UserCohort(Enum):
    """Define user segments for analysis"""
    FREE = "free"                    # Free tier users
    PAID = "paid"                    # Standard paid plan
    ENTERPRISE = "enterprise"        # Enterprise customers
    NEW = "new"                      # <7 days since signup
    POWER = "power"                  # >100 queries/month
    AT_RISK = "at_risk"              # Usage declined >30% this week

# Queries per cohort
cohort_queries = Counter(
    'rag_cohort_queries_total',
    'Queries by user cohort',
    ['cohort', 'feature_used']
)

# Active users per cohort (gauge, updated periodically)
cohort_active_users = Gauge(
    'rag_cohort_active_users',
    'Active users in last 24h by cohort',
    ['cohort']
)

# Retention rate by cohort (gauge showing %)
cohort_retention_rate = Gauge(
    'rag_cohort_retention_rate',
    '7-day retention rate by cohort (%)',
    ['cohort']
)

# Average queries per user by cohort
cohort_avg_queries = Gauge(
    'rag_cohort_avg_queries_per_user',
    'Average queries per user in cohort',
    ['cohort', 'time_window']  # '24h', '7d', '30d'
)

# Cohort-specific costs
cohort_cost = Counter(
    'rag_cohort_cost_usd',
    'Total cost (USD) by cohort',
    ['cohort', 'cost_type']  # 'embedding', 'llm', 'vector_db'
)

# Function to determine user cohort dynamically
def get_user_cohort(
    user_id: str,
    plan: str,
    days_since_signup: int,
    queries_this_month: int,
    queries_last_week: int,
    queries_two_weeks_ago: int
) -> UserCohort:
    """
    Dynamically classify user into cohort based on behavior.
    
    In production, this would query your user database/cache.
    """
    # Check usage patterns
    if queries_this_month > 100:
        return UserCohort.POWER
    
    if days_since_signup <= 7:
        return UserCohort.NEW
    
    # Check for at-risk (usage declined >30%)
    if queries_two_weeks_ago > 0:
        decline = (queries_two_weeks_ago - queries_last_week) / queries_two_weeks_ago
        if decline > 0.3:
            return UserCohort.AT_RISK
    
    # Check plan type
    if plan == "enterprise":
        return UserCohort.ENTERPRISE
    elif plan == "paid":
        return UserCohort.PAID
    else:
        return UserCohort.FREE

# Example: Recording cohort-based query
def record_cohort_query(
    user_id: str,
    feature_used: str,
    cost_embedding: float,
    cost_llm: float,
    cost_vector_db: float,
    **user_data  # Days since signup, query counts, etc.
):
    """Record query with cohort context"""
    cohort = get_user_cohort(user_id, **user_data)
    
    # Increment query counter
    cohort_queries.labels(
        cohort=cohort.value,
        feature_used=feature_used
    ).inc()
    
    # Track costs by cohort
    cohort_cost.labels(cohort=cohort.value, cost_type='embedding').inc(cost_embedding)
    cohort_cost.labels(cohort=cohort.value, cost_type='llm').inc(cost_llm)
    cohort_cost.labels(cohort=cohort.value, cost_type='vector_db').inc(cost_vector_db)
```

**Why cohort analysis matters:**
- **Cost optimization:** Discover which cohorts are unprofitable (high cost, low value)
- **Feature prioritization:** See what power users vs. new users actually use
- **Churn prevention:** Identify at-risk users BEFORE they churn
- **Pricing decisions:** Data to justify plan pricing based on usage patterns

**Key insight:** The `get_user_cohort()` function runs ON EVERY QUERY. It must be fast (<10ms). In production:
- Cache user metadata in Redis
- Precompute cohorts nightly and store in database
- Use simple heuristics (don't run complex SQL per query)

### Step 3: Feature Usage Tracking (4 minutes)

[SLIDE: Step 3 Overview]

Track which RAG features users actually use (vs. what you built).

```python
# business_metrics.py (continued)

# ============================================================
# SECTION 3: FEATURE USAGE METRICS
# ============================================================

class RAGFeature(Enum):
    """Define trackable features in your RAG system"""
    SIMPLE_QA = "simple_qa"                  # Basic question answering
    SUMMARIZATION = "summarization"          # Document summarization
    MULTI_DOC = "multi_doc"                  # Multi-document synthesis
    CHAT_HISTORY = "chat_history"            # Multi-turn conversation
    FILTERING = "filtering"                  # Metadata filtering
    HYBRID_SEARCH = "hybrid_search"          # Dense + sparse search

# Feature usage counter
feature_usage = Counter(
    'rag_feature_usage_total',
    'Feature usage counts',
    ['feature', 'user_cohort']
)

# Feature success rate (% of queries where feature worked)
feature_success_rate = Gauge(
    'rag_feature_success_rate',
    'Feature success rate (%)',
    ['feature']
)

# Time spent in each feature (helps identify slow features)
feature_duration = Histogram(
    'rag_feature_duration_seconds',
    'Time spent in feature',
    ['feature'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Feature adoption rate (% of users using feature)
feature_adoption = Gauge(
    'rag_feature_adoption_rate',
    'Percentage of active users using feature',
    ['feature']
)

# Example: Tracking feature usage
def track_feature_usage(
    feature: RAGFeature,
    user_cohort: str,
    duration_seconds: float,
    success: bool
):
    """Track feature usage metrics"""
    # Increment usage counter
    feature_usage.labels(
        feature=feature.value,
        user_cohort=user_cohort
    ).inc()
    
    # Record duration
    feature_duration.labels(
        feature=feature.value
    ).observe(duration_seconds)
    
    # Update success rate (in production, calculate from time window)
    if success:
        current_rate = feature_success_rate.labels(feature=feature.value)._value._value
        # Simple moving average (in production, use proper time-window calc)
        feature_success_rate.labels(feature=feature.value).set(
            current_rate * 0.95 + (1.0 if success else 0.0) * 0.05
        )
```

**Why track feature usage:**
- **Identify unused features:** You built multi-doc synthesis but only 2% of queries use it
- **Optimize high-traffic features:** 80% of queries use simple Q&A—make it fast
- **Justify development:** Data-driven decisions on what to build next
- **Pricing strategy:** Premium features should show high engagement in paid cohorts

**Real production example:** A SaaS RAG company built 5 advanced features but found 90% of users only used basic Q&A. They deprecated 3 features, simplified pricing, and cut infrastructure costs by 40%.

### Step 4: Executive KPI Dashboard (6 minutes)

[SLIDE: Step 4 Overview]

Now let's translate these metrics into executive-friendly KPIs.

```python
# business_metrics.py (continued)

# ============================================================
# SECTION 4: EXECUTIVE KPI METRICS
# ============================================================

# Revenue attribution (if you have revenue data)
revenue_attributed = Counter(
    'rag_revenue_attributed_usd',
    'Revenue attributed to RAG queries (USD)',
    ['user_cohort', 'feature_used']
)

# Cost per user (rolling calculation)
cost_per_user = Gauge(
    'rag_cost_per_user_usd',
    'Average cost per user (USD) in last 24h',
    ['user_cohort']
)

# Return on AI investment (ROAI)
roai_metric = Gauge(
    'rag_roai_ratio',
    'Return on AI Investment (Revenue / AI Costs)',
    ['time_window']  # '24h', '7d', '30d'
)

# User engagement score (composite metric)
engagement_score = Gauge(
    'rag_user_engagement_score',
    'Composite engagement score (0-100)',
    ['user_cohort']
)

# Net Promoter Score (NPS) equivalent
nps_score = Gauge(
    'rag_nps_score',
    'Net Promoter Score (-100 to 100)',
    []  # Global metric
)

# Function to calculate KPIs from base metrics
def calculate_kpis():
    """
    Background job to calculate executive KPIs from base metrics.
    
    Run this every 5-15 minutes to update dashboard KPIs.
    """
    # In production, you'd query Prometheus for these calculations
    # For demo, showing the logic:
    
    # Example: Cost per user
    total_cost = sum([
        # Query Prometheus for sum of costs in last 24h
        # rate(rag_cohort_cost_usd[24h]) * 86400
    ])
    active_users = sum([
        # Query Prometheus for active users
        # rag_cohort_active_users
    ])
    if active_users > 0:
        cost_per_user.labels(user_cohort='all').set(total_cost / active_users)
    
    # Example: ROAI (Return on AI Investment)
    revenue = sum([
        # Query your billing system or rag_revenue_attributed_usd
    ])
    ai_costs = sum([
        # OpenAI costs + Pinecone costs + infrastructure
    ])
    if ai_costs > 0:
        roai_metric.labels(time_window='24h').set(revenue / ai_costs)
    
    # Example: Engagement score (composite)
    # Combine: queries per user, satisfaction, feature usage diversity
    avg_queries = 10  # From metrics
    avg_satisfaction = 4.2  # From satisfaction_score
    feature_diversity = 3  # Number of features used
    
    engagement = (
        (avg_queries / 20) * 30 +  # 30 points for query volume
        (avg_satisfaction / 5) * 50 +  # 50 points for satisfaction
        (feature_diversity / 5) * 20   # 20 points for feature diversity
    )
    engagement_score.labels(user_cohort='all').set(min(100, engagement))

# Integration with your RAG API
from fastapi import FastAPI, BackgroundTasks
from prometheus_client import make_asgi_app

app = FastAPI()

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.post("/api/query")
async def rag_query(
    query: str,
    user_id: str,
    background_tasks: BackgroundTasks
):
    """
    RAG query endpoint with business metrics instrumentation.
    """
    # Your existing RAG logic here
    # ...
    
    # After query completes, record business metrics
    background_tasks.add_task(
        record_query_outcome,
        user_id=user_id,
        user_cohort="paid",  # Lookup from user DB
        model="gpt-4",
        outcome=QueryOutcome.ACCURATE,
        confidence=0.87
    )
    
    background_tasks.add_task(
        track_feature_usage,
        feature=RAGFeature.SIMPLE_QA,
        user_cohort="paid",
        duration_seconds=1.2,
        success=True
    )
    
    return {"answer": "..."}

# Background job to calculate KPIs
import asyncio

async def kpi_calculator_job():
    """Run KPI calculations every 5 minutes"""
    while True:
        calculate_kpis()
        await asyncio.sleep(300)  # 5 minutes

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(kpi_calculator_job())
```

**Key decisions in KPI design:**
- **Aggregate base metrics:** Don't reinvent the wheel—combine existing metrics
- **Background calculation:** KPIs update every 5-15 minutes (not real-time)
- **Composite scores:** Engagement score combines multiple signals into one number
- **Executive language:** Use terms executives understand (ROAI, NPS, engagement)

### Step 5: Grafana Executive Dashboard (5 minutes)

[SLIDE: Step 5 Overview - Grafana Configuration]

Finally, create the executive dashboard in Grafana.

**[SCREEN: Grafana UI]**

```json
// grafana_executive_dashboard.json

{
  "dashboard": {
    "title": "RAG Executive KPIs",
    "panels": [
      {
        "title": "User Satisfaction (7-Day Trend)",
        "targets": [{
          "expr": "avg(rag_satisfaction_score) by (user_cohort)",
          "legendFormat": "{{user_cohort}}"
        }],
        "type": "graph"
      },
      {
        "title": "Cost Per User (by Cohort)",
        "targets": [{
          "expr": "rag_cost_per_user_usd",
          "legendFormat": "{{user_cohort}}"
        }],
        "type": "singlestat",
        "format": "currency"
      },
      {
        "title": "Return on AI Investment (ROAI)",
        "targets": [{
          "expr": "rag_roai_ratio{time_window='7d'}",
          "legendFormat": "7-Day ROAI"
        }],
        "type": "gauge",
        "thresholds": {
          "0": "red",    // ROAI < 1 (losing money)
          "1": "yellow", // ROAI = 1-2 (break-even to profitable)
          "2": "green"   // ROAI > 2 (highly profitable)
        }
      },
      {
        "title": "Feature Adoption (% of Users)",
        "targets": [{
          "expr": "rag_feature_adoption_rate",
          "legendFormat": "{{feature}}"
        }],
        "type": "bar"
      },
      {
        "title": "Cohort Retention (7-Day)",
        "targets": [{
          "expr": "rag_cohort_retention_rate",
          "legendFormat": "{{cohort}}"
        }],
        "type": "table"
      },
      {
        "title": "Hallucination Rate (24h Rolling)",
        "targets": [{
          "expr": "rag_hallucination_rate",
          "legendFormat": "{{model}}"
        }],
        "type": "graph",
        "alert": {
          "condition": "WHEN avg() OF query(A, 5m, now) IS ABOVE 5",
          "message": "Hallucination rate >5% for {{model}}"
        }
      }
    ],
    "refresh": "5m",  // Auto-refresh every 5 minutes
    "time": {
      "from": "now-7d",
      "to": "now"
    }
  }
}
```

**Dashboard design principles:**
- **Top row:** High-level KPIs (satisfaction, ROAI, engagement)
- **Middle row:** Cohort comparisons (who's doing what)
- **Bottom row:** Operational details (feature usage, costs)
- **Time ranges:** Default to 7 days (executives think in weeks/months, not hours)
- **Alerts:** Highlight problems (hallucination rate >5%, ROAI <1)

**Import this dashboard:**
```bash
# Import into Grafana
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana_executive_dashboard.json \
  -u admin:admin
```

### Final Integration & Testing

[SCREEN: Terminal running tests]

**NARRATION:**
"Let's verify everything works end-to-end:

```bash
# 1. Start your FastAPI app with metrics
python main.py

# 2. Send test queries with different cohorts
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Test question", "user_id": "paid_user_123"}'

# 3. Check metrics endpoint
curl http://localhost:8000/metrics | grep "rag_"

# Expected output:
# rag_query_accuracy_total{outcome="accurate",model="gpt-4",user_cohort="paid"} 1.0
# rag_satisfaction_score_bucket{user_cohort="paid",feature_used="simple_qa",le="5.0"} 1.0
# rag_cohort_queries_total{cohort="paid",feature_used="simple_qa"} 1.0
```

**If you see errors:**
- `ModuleNotFoundError`: Reinstall prometheus_client
- `Metrics not appearing`: Check FastAPI mounted metrics_app correctly
- `Dashboard shows no data`: Verify Prometheus is scraping localhost:8000/metrics

**Verification checklist:**
- ✅ Metrics appear at /metrics endpoint
- ✅ Prometheus scraping (check Prometheus targets page)
- ✅ Grafana dashboard shows data
- ✅ KPI calculations running in background

Your system now tracks business metrics alongside technical metrics."

---

## SECTION 5: REALITY CHECK (3-4 minutes) **[CRITICAL]**

**[28:00-31:30] What Custom Business Metrics DOESN'T Do**

[SLIDE: "Reality Check: The Cost of Custom Metrics"]

**NARRATION:**
"Let's be completely honest about what we just built. Custom business metrics are powerful, BUT they're not magic. Here's what you need to know before deploying this to production.

### What This DOESN'T Do:

1. **Doesn't work out of the box—requires significant instrumentation effort**
   - You must modify EVERY query handler to record business context
   - Each new feature needs new metric definitions and dashboard panels
   - Cohort logic must be maintained as user behavior evolves
   - Example: Adding 'team collaboration' feature means updating 5+ metric definitions, 3 dashboard panels, and cohort classification logic
   - Workaround: Plan 1-2 days per new feature for metrics instrumentation

2. **Doesn't automatically prevent metric cardinality explosion**
   - Easy to accidentally create millions of time series with wrong labels
   - Example: Using user_id as label instead of user_cohort creates 10K+ series
   - Prometheus storage fills up, queries timeout, dashboards crash
   - Why this exists: No built-in validation prevents high-cardinality labels
   - Impact: Production outage when Prometheus runs out of disk space (typically 2-3 days with bad labels)

3. **Doesn't replace proper product analytics for complex cohort analysis**
   - Can't do funnel analysis (signup → first query → paid conversion)
   - Can't track user journey across sessions (Prometheus doesn't store events)
   - Can't A/B test feature variants (no experiment framework)
   - When you'll hit this: When executives ask 'What % of free users upgrade after using feature X?'—you can't answer with Prometheus alone
   - What to do instead: Use Mixpanel/Amplitude for user journeys, keep Prometheus for operational metrics

### Trade-offs You Accepted:

- **Complexity:** Added 300+ lines of metric instrumentation code across your codebase, new background job for KPI calculation, 5+ new Grafana dashboards to maintain
- **Performance:** Each query now records 3-5 metrics (adds 5-10ms overhead), background jobs query Prometheus every 5 minutes (adds CPU load)
- **Cost:** ClickHouse for advanced analytics costs $100-500/month, increased Prometheus storage from metric growth ($20-50/month), engineering time to maintain (2-4 hours/month)

### When This Approach Breaks:

This is the right solution for **1K-100K queries/month** with **simple cohort definitions** (3-5 cohorts). 

It breaks down when you hit:
- **>100K queries/month:** Prometheus cardinality explodes, need time-series database like InfluxDB or Timescale
- **Complex cohorts (>10 dimensions):** Can't fit cohort logic in label space, need data warehouse like Snowflake
- **Real-time KPIs required:** Prometheus scrapes every 15s, executives want real-time dashboards updated every second—need streaming pipeline (Kafka + Flink)
- **Cross-platform analytics:** Need to join RAG metrics with CRM (Salesforce), billing (Stripe), support tickets (Zendesk)—Prometheus can't do joins, need full BI platform

**Bottom line:** This is the right solution for startups and small-to-medium SaaS companies (10-1000 users) who want business visibility without Mixpanel's $1000/month cost. But if you're scaling to enterprise (10K+ users) or need sophisticated analytics, invest in a proper product analytics platform. We'll discuss alternatives next."

---

## SECTION 6: ALTERNATIVE SOLUTIONS (4-5 minutes) **[CRITICAL]**

**[31:30-36:00] Other Ways to Track Business Metrics**

[SLIDE: "Alternative Approaches: Comparing Options"]

**NARRATION:**
"The custom Prometheus approach we just built isn't the only way to track business metrics. Let's look at three alternatives so you can make an informed decision based on your scale, budget, and requirements.

### Alternative 1: Product Analytics Platforms (Mixpanel, Amplitude, Heap)

**Best for:** Companies with $1000+/month budget, need advanced cohort analysis, want no-code analytics

**How it works:**
These platforms capture every user event (query submitted, rating given, feature clicked) and provide powerful UI for cohort analysis, funnels, retention curves.

```python
# Mixpanel integration example
from mixpanel import Mixpanel

mp = Mixpanel("YOUR_PROJECT_TOKEN")

# Track query with rich context
mp.track("user_123", "Query Submitted", {
    "query": "What is GDPR?",
    "satisfaction": 5,
    "feature_used": "summarization",
    "cohort": "paid",
    "answer_confidence": 0.92
})

# Mixpanel UI then lets you:
# - Create cohorts with no code (e.g., "Paid users who rated >4")
# - Build funnels (signup → first query → upgraded)
# - Analyze retention (7-day, 30-day retention curves)
```

**Trade-offs:**
- ✅ **Pros:** 
  - No code needed for complex analytics (drag-and-drop UI)
  - Advanced features: funnels, journeys, A/B testing built-in
  - Scales to millions of events without infrastructure management
  - Real-time dashboards (updates instantly, not every 15s)
- ❌ **Cons:** 
  - Expensive ($1000-5000/month for 10K users, $10K+/month at scale)
  - Vendor lock-in (can't export raw data easily)
  - Slow to adopt new metrics (must wait for UI updates)
  - Doesn't integrate with Prometheus (separate monitoring stack)

**Cost:** $1000/month (10K users) → $5000/month (100K users) → $15K+/month (1M+ users)

**Example use case:** You're a well-funded startup (raised Series A), have product analytics team, need to prove user engagement metrics to investors

**Choose this if:**
- Budget >$1000/month for analytics
- Need no-code analytics for non-technical team (product managers, executives)
- Want advanced cohort analysis (>10 cohort dimensions, funnel tracking)
- Scaling rapidly (10K+ new users/month) and need platform that scales with you

---

### Alternative 2: Business Intelligence (BI) Tools (Looker, Tableau, Metabase)

**Best for:** Companies with existing data warehouse, need custom SQL queries, want executive reporting

**How it works:**
Export metrics to data warehouse (BigQuery, Snowflake, PostgreSQL), use BI tool to query and visualize.

```python
# Export Prometheus metrics to PostgreSQL
from prometheus_api_client import PrometheusConnect
import psycopg2

prom = PrometheusConnect(url="http://localhost:9090")
conn = psycopg2.connect("dbname=analytics user=postgres")

# Query Prometheus, insert into Postgres
query = "rag_satisfaction_score"
data = prom.custom_query(query=query)

cursor = conn.cursor()
for result in data:
    cursor.execute(
        "INSERT INTO rag_metrics (metric, value, labels, timestamp) VALUES (%s, %s, %s, %s)",
        (query, result['value'], result['metric'], result['timestamp'])
    )
conn.commit()
```

Then connect Looker/Tableau to PostgreSQL and build dashboards with SQL.

**Trade-offs:**
- ✅ **Pros:** 
  - Full SQL flexibility (join with billing, CRM, support data)
  - Executive-friendly dashboards (polished UI, scheduled emails)
  - One-time cost or lower monthly cost than Mixpanel ($500-2000/month)
  - Own your data (stored in your warehouse)
- ❌ **Cons:** 
  - Requires data engineering (ETL pipelines to move data)
  - Dashboards lag behind real-time (typically 1-24 hour delay)
  - Complex setup (need warehouse + ETL + BI tool)
  - SQL knowledge required (non-technical users can't self-serve)

**Cost:** 
- Looker: $5000-10K/month (enterprise)
- Tableau: $70/user/month ($840/year per user)
- Metabase: Free (open-source) or $85/month (hosted)
- Plus data warehouse: $100-1000/month (BigQuery/Snowflake)

**Example use case:** You already have Snowflake for analytics, finance team wants to analyze cost per user alongside revenue from Stripe

**Choose this if:**
- Have data engineering team (can build ETL)
- Need to join RAG metrics with external data (billing, CRM, support)
- Executives want polished reports, not operational dashboards
- Budget $1000-3000/month total (BI tool + warehouse)

---

### Alternative 3: Simple Daily/Weekly Reports (Manual Aggregation)

**Best for:** Startups <100 users, limited engineering resources, MVP validation phase

**How it works:**
Write Python script that queries Prometheus once per day, calculates KPIs, sends email/Slack report.

```python
# daily_report.py

from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

prom = PrometheusConnect(url="http://localhost:9090")

def generate_daily_report():
    """Generate daily business metrics report"""
    yesterday = datetime.now() - timedelta(days=1)
    
    # Query Prometheus for key metrics
    total_queries = prom.custom_query(
        query=f'sum(increase(rag_cohort_queries_total[1d]))'
    )[0]['value'][1]
    
    avg_satisfaction = prom.custom_query(
        query=f'avg(rag_satisfaction_score)'
    )[0]['value'][1]
    
    hallucination_rate = prom.custom_query(
        query=f'avg(rag_hallucination_rate)'
    )[0]['value'][1]
    
    # Format report
    report = f"""
    Daily RAG Metrics Report - {yesterday.strftime('%Y-%m-%d')}
    
    📊 Usage:
    - Total Queries: {total_queries}
    - Active Users: [manual count from DB]
    
    ⭐ Quality:
    - Avg Satisfaction: {avg_satisfaction:.2f}/5
    - Hallucination Rate: {hallucination_rate:.1f}%
    
    💰 Costs:
    - Total Spend: [manual calc from OpenAI/Pinecone bills]
    - Cost per Query: [manual calc]
    
    Top Issues:
    - [Manually identified from support tickets]
    """
    
    # Send via email
    msg = MIMEText(report)
    msg['Subject'] = f'RAG Metrics - {yesterday.strftime('%m/%d')}'
    msg['From'] = 'metrics@company.com'
    msg['To'] = 'exec@company.com'
    
    smtp = smtplib.SMTP('localhost')
    smtp.send_message(msg)
    smtp.quit()

# Run via cron: 0 9 * * * python daily_report.py
```

**Trade-offs:**
- ✅ **Pros:** 
  - Dead simple (50 lines of Python)
  - Zero cost (uses existing Prometheus)
  - No new tools to learn or maintain
  - Good enough for early-stage validation
- ❌ **Cons:** 
  - Manual effort (update script for new metrics)
  - No historical analysis (just point-in-time snapshots)
  - No drill-down (can't explore 'why satisfaction dropped')
  - Not actionable (just data, no alerts or insights)

**Cost:** $0/month (just cron job + email)

**Example use case:** You're a solo founder with 50 beta users, need weekly metrics to share with advisors/investors, can't justify $1000/month Mixpanel yet

**Choose this if:**
- <100 users (small scale)
- Metrics reviewed weekly, not daily (slow cadence OK)
- Technical founder who can update Python script
- Pre-PMF (validating product, not scaling)

---

## DECISION FRAMEWORK: Which Approach to Choose?

[SLIDE: Decision Tree]

**Use this flowchart:**

```
START: Need business metrics for RAG system?
│
├─ <100 users, MVP stage?
│  └─ YES → Simple Daily Reports ($0/month)
│  └─ NO → Continue
│
├─ Have data engineering team + data warehouse?
│  └─ YES → BI Tools (Looker/Tableau, $1K-3K/month)
│  └─ NO → Continue
│
├─ Budget >$1000/month for analytics?
│  └─ YES → Product Analytics Platform (Mixpanel/Amplitude)
│  └─ NO → Continue
│
├─ 1K-100K queries/month, simple cohorts?
│  └─ YES → Custom Prometheus Metrics (today's approach, $100-200/month)
│  └─ NO → BI Tools or Product Analytics
```

**Summary table:**

| Approach | Cost | Setup Time | Best For | Avoid When |
|----------|------|------------|----------|------------|
| **Custom Prometheus** | $100-200/month | 2-3 days | 1K-100K queries, simple cohorts | >100K queries, complex funnels |
| **Mixpanel/Amplitude** | $1K-5K/month | 1 day | No-code analytics, advanced cohorts | Budget <$1000/month |
| **BI Tools (Looker)** | $1K-3K/month | 1-2 weeks | Join with external data, executive reports | No data warehouse |
| **Simple Reports** | $0/month | 4 hours | <100 users, MVP validation | Need real-time dashboards |

**Why we chose Custom Prometheus for this video:**
- Builds on existing M2.3 infrastructure (no new tools)
- Handles 1K-100K queries/month (most Level 2 learners' scale)
- Cost-effective ($100-200/month vs. $1000+/month for platforms)
- Teaches valuable metric instrumentation skills (transferable to any system)

**When to switch:**
- **>100K queries/month** → Migrate to BI tool + data warehouse
- **Need funnels/journeys** → Add Mixpanel alongside Prometheus
- **<10 users, early MVP** → Start with Simple Reports, upgrade later"

---

## SECTION 7: WHEN NOT TO USE (2-3 minutes) **[CRITICAL]**

**[36:00-38:30] Anti-Patterns: When Custom Metrics Are the Wrong Choice**

[SLIDE: "When NOT to Use Custom Prometheus Metrics"]

**NARRATION:**
"Here are three specific scenarios where custom Prometheus metrics are the WRONG approach—and what to use instead.

### Scenario 1: You Have <100 Users and No Product-Market Fit Yet

**Specific conditions:**
- <100 active users
- Product still pivoting (features changing weekly)
- No clear success metrics yet (experimenting)
- Engineering team <3 people

**Why it fails:**
You'll spend 2-3 days instrumenting metrics, then pivot and all those metrics become irrelevant. New feature = rewrite all metric definitions.

Technical reason: Custom metrics have HIGH MAINTENANCE COST (update every time product changes). With frequent pivots, you're constantly rewriting metric code instead of building product.

**Use instead:** Simple Daily Reports (Alternative 3)
- Python script queries Prometheus once daily
- Calculate 3-5 core metrics (queries, satisfaction, cost)
- Email report to team
- When product stabilizes and you hit 100+ users, upgrade to custom metrics

**Red flag:** You're building dashboards for metrics you'll deprecate next month

---

### Scenario 2: You Need User Funnels or Journey Analysis

**Specific conditions:**
- Need to track user journey: signup → first query → paid conversion
- Want to analyze drop-off points (where users churn)
- Require cohort comparison of behavior over time
- A/B testing feature variants

**Why it fails:**
Prometheus doesn't store individual events—it aggregates to time-series. You can't answer: 'What % of users who used feature X upgraded within 7 days?'

Technical reason: Prometheus metrics are AGGREGATED. They show totals/averages, not individual user paths. To track funnels, you need event-based analytics that stores every user action with timestamps.

Example that won't work:
```python
# ❌ Can't do this with Prometheus
# "Show me users who: did action A → action B → action C within 24 hours"
# Prometheus only knows: "10 people did A, 8 did B, 5 did C" (no linkage)
```

**Use instead:** Product Analytics Platform (Alternative 1)
- Mixpanel tracks individual user events
- Built-in funnel analysis: signup → query → upgrade
- Cohort retention curves (7-day, 30-day)
- A/B testing framework included

Cost: $1000-2000/month, but saves 2+ weeks of engineering time trying to hack funnels into Prometheus

**Red flag:** You're trying to store user IDs in Prometheus labels to track journeys (leads to cardinality explosion)

---

### Scenario 3: You're Scaling Beyond 100K Queries/Month

**Specific conditions:**
- >100K queries/month (or >3K/hour sustained)
- Cohort definitions complex (>10 dimensions: plan, usage tier, industry, region, feature set, etc.)
- Need to join RAG metrics with external data (Salesforce CRM, Stripe billing, Zendesk support)
- Real-time dashboards required (<1 second update latency)

**Why it fails:**
Prometheus cardinality explodes (>1M time series), queries timeout, dashboards become unusable. Also, Prometheus can't join with external data sources.

Technical reason at scale: Each unique label combination creates a new time series. With 10 cohort dimensions and 10 values each, you have 10^10 potential combinations. Prometheus can't handle >1M active series efficiently.

Example breakdown:
- 10 cohort dimensions × 10 values each = 10 billion potential label combinations
- Prometheus recommended limit: 1 million time series
- Your actual usage will create ~5-10M series → Prometheus crashes

**Use instead:** BI Tool + Data Warehouse (Alternative 2)
- Export metrics to data warehouse (BigQuery, Snowflake)
- Use Looker/Tableau for complex queries and joins
- Join RAG metrics with Stripe revenue, Salesforce accounts, Zendesk tickets
- Scales to billions of events

Architecture:
```
Prometheus (keep for technical metrics)
    â†"
Export to BigQuery (daily)
    â†"
Join with CRM, billing, support data
    â†"
Looker dashboards for executives
```

Cost: $1000-3000/month, but necessary at this scale

**Red flag:** Your Prometheus server crashes weekly from cardinality, queries timeout after 30 seconds

---

**Quick reference anti-patterns:**

❌ <100 users → Use Simple Reports instead  
❌ Need funnels → Use Mixpanel instead  
❌ >100K queries/month → Use BI tool + warehouse instead  
❌ Complex cohorts (>10 dimensions) → Use warehouse instead  
❌ Need real-time (<1s updates) → Use streaming (Kafka) instead  

**Remember:** Custom Prometheus metrics are the sweet spot for 1K-100K queries/month with simple cohorts (3-5 dimensions). Outside that range, choose alternatives."

---

## SECTION 8: COMMON FAILURES (5-7 minutes) **[CRITICAL]**

**[38:30-45:30] When Business Metrics Go Wrong**

[SLIDE: "Common Failures with Custom Metrics"]

**NARRATION:**
"Now for the most important part: the five production failures you WILL encounter and how to debug them. I'm showing you the exact error messages, reproduction steps, and fixes.

---

#### Failure #1: Metric Cardinality Explosion (Prometheus Storage Full)

**[38:30] Let me reproduce this disaster:**

[TERMINAL: Show Python script creating unbounded metrics]

```python
# cardinality_explosion_demo.py

from prometheus_client import Counter
import uuid

# ❌ BAD: Using unbounded label (user_id)
user_queries = Counter(
    'rag_queries_by_user',
    'Queries per user',
    ['user_id', 'query_text']  # Each unique user + query = new time series!
)

# This creates thousands of time series
for i in range(10000):
    user_id = str(uuid.uuid4())  # Unique user ID
    query = f"Query {i}"
    user_queries.labels(user_id=user_id, query_text=query).inc()

print(f"Created {10000} time series!")
```

**Error message you'll see:**

[TERMINAL: Prometheus logs]
```bash
level=error ts=2025-11-02T10:23:45.123Z caller=db.go:892 component=tsdb msg="compaction failed" err="write /prometheus/data/01H8X9Y2Z3/chunks/000123: no space left on device"

Prometheus storage: 98% full (49.2GB / 50GB)
Time series count: 2,847,392 (limit: 1,000,000)
Cardinality explosion detected in metric: rag_queries_by_user
```

**What this means:**
Each unique combination of label values (user_id + query_text) creates a separate time series. With 10K users × 100 unique queries = 1M time series. Prometheus stores each series separately, filling disk in hours/days.

**How to fix it:**

[CODE: "cardinality_fix.py"]
```python
# ✅ GOOD: Use bounded labels only
user_queries = Counter(
    'rag_queries_by_cohort',
    'Queries by user cohort',
    ['user_cohort', 'feature_used']  # Only 3 cohorts × 5 features = 15 series
)

# Record query with cohort, not individual user ID
user_queries.labels(
    user_cohort='paid',  # Bounded: free, paid, enterprise
    feature_used='simple_qa'  # Bounded: 5 features
).inc()

# Put high-cardinality data (user_id, query_text) in logs, NOT metrics
import logging
logger.info("Query processed", extra={
    'user_id': user_id,
    'query_text': query_text,
    'cohort': 'paid'
})
```

**How to verify the fix:**

[TERMINAL]
```bash
# Check Prometheus cardinality
curl http://localhost:9090/api/v1/status/tsdb | jq '.data.numSeries'
# Should be <10,000 for most apps

# Check specific metric cardinality
curl -s http://localhost:9090/api/v1/label/__name__/values | \
  grep "rag_queries" | wc -l
# Should show small number (<50)

# Monitor disk usage
df -h /prometheus/data
# Should stabilize, not grow unbounded
```

**How to prevent:**
- ✅ Never use labels with >100 possible values
- ✅ User IDs, timestamps, UUIDs → logs, not metrics
- ✅ Review label cardinality before production: `cardinality(metric_name)`
- ✅ Set Prometheus alerts on time series count: `prometheus_tsdb_symbol_table_size_bytes > 1000000`

**When this happens:**
Week 2-3 after launching custom metrics, when production traffic hits 1000+ users. Suddenly Prometheus crashes with 'no space left on device.'

---

#### Failure #2: Dashboard Performance Issues (Grafana Queries Timeout)

**[40:30] Watch this dashboard destroy itself:**

[SCREEN: Grafana dashboard loading... timeout]

```json
// slow_dashboard_query.json (❌ BAD QUERY)

{
  "title": "User Satisfaction Over Time",
  "targets": [{
    "expr": "avg(rag_satisfaction_score{user_cohort='paid'}) by (user_id)",
    //                                                              ^^^^^^^^
    // ❌ Problem: Grouping by user_id (high cardinality)
    "range": true,
    "start": "-30d"  // ❌ Problem: 30-day range is too wide
  }]
}
```

**Error message you'll see:**

[GRAFANA ERROR POPUP]
```
Query timeout after 60s
Expression: avg(rag_satisfaction_score{user_cohort='paid'}) by (user_id)
Error: context deadline exceeded

Prometheus query stats:
- Time series evaluated: 142,938
- Samples processed: 41,293,482
- Query took: 61.2 seconds (timeout at 60s)
```

**What this means:**
You're asking Prometheus to load 30 days of data for 142K users, calculate average per user, then render. That's 41 million data points. The query evaluates every sample across the full time range. With high-cardinality grouping (`by (user_id)`), this overwhelms Prometheus query engine.

**How to fix it:**

[CODE: "fast_dashboard_query.json"]
```json
// ✅ GOOD QUERY - Aggregated and narrow window

{
  "title": "User Satisfaction (by Cohort)",
  "targets": [{
    "expr": "avg(rate(rag_satisfaction_score_sum[5m])) by (user_cohort)",
    //      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    // ✅ Fix 1: Use rate() over 5-minute window (not raw values)
    // ✅ Fix 2: Group by user_cohort (3 values), not user_id (thousands)
    "range": true,
    "start": "-7d"  // ✅ Fix 3: Narrower time range (7 days, not 30)
  }]
}
```

**Alternative for long-term trends:** Use recording rules

```yaml
# prometheus.yml - Recording rules for expensive queries

groups:
  - name: rag_recording_rules
    interval: 1m  # Calculate every minute
    rules:
      - record: rag:satisfaction:5m_avg_by_cohort
        expr: avg(rate(rag_satisfaction_score_sum[5m])) by (user_cohort)
      
      - record: rag:cost_per_user:1h_avg
        expr: |
          sum(rate(rag_cohort_cost_usd[1h])) by (user_cohort)
          /
          sum(rag_cohort_active_users) by (user_cohort)
```

Then query the recording rule in Grafana:
```json
{
  "expr": "rag:satisfaction:5m_avg_by_cohort"  // Pre-calculated, fast
}
```

**How to verify the fix:**

[TERMINAL]
```bash
# Test query performance locally
time curl -g 'http://localhost:9090/api/v1/query?query=avg(rate(rag_satisfaction_score_sum[5m]))%20by%20(user_cohort)'

# Should return in <2 seconds
# Output: real 0m0.872s

# Check query stats in Prometheus UI
# Go to http://localhost:9090/graph
# Paste query, check "Stats" tab:
# - Execution time: <1s ✅
# - Total samples: <10,000 ✅
```

**How to prevent:**
- ✅ Use 5-15 minute windows for rate(), not hours/days
- ✅ Group by low-cardinality labels only (cohort, feature, model)
- ✅ Create recording rules for complex queries
- ✅ Test queries with prometheus_api_client before adding to Grafana

**When this happens:**
Week 1-2 after creating executive dashboard. Executives complain 'dashboard won't load' because you used 30-day range with high-cardinality grouping.

---

#### Failure #3: Inaccurate Cohort Definitions (Wrong User Segmentation)

**[42:30] This looks right but classifies users incorrectly:**

[CODE: "inaccurate_cohort.py"]
```python
# ❌ BAD: Naive cohort classification

def get_user_cohort(queries_this_month: int) -> str:
    """Classify user into power/normal/light"""
    if queries_this_month > 100:
        return "power"
    elif queries_this_month > 10:
        return "normal"
    else:
        return "light"

# Problem: Doesn't account for account age
# A user who signed up yesterday with 15 queries is VERY different 
# from a user who's been around 6 months with 15 queries

# Result: Your "power user" cohort mixes:
# - New users having onboarding burst (150 queries in week 1, then 10/month)
# - True power users (sustained 120+ queries/month)

# This makes cohort analysis meaningless!
```

**Error message you'll see:**

[DASHBOARD: Confusing cohort behavior]
```
Dashboard shows:
- Power user cohort retention: 12% (should be 80%+)
- Power users cost per query: $0.02 (2x normal users)

You investigate and find:
- 80% of "power users" only stayed 1 week (onboarding burst, then churned)
- Actual sustained power users: 20% of the cohort
- Mixing these groups makes metrics useless
```

**What this means:**
Cohort classification logic is TOO SIMPLE. It doesn't account for:
- Account age (new vs. veteran users)
- Query pattern over time (burst vs. sustained)
- Features used (quality signal, not just quantity)

Result: Cohorts are heterogeneous (contain very different user types), making analysis misleading.

**How to fix it:**

[CODE: "accurate_cohort.py"]
```python
# ✅ GOOD: Multi-dimensional cohort classification

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

@dataclass
class UserActivity:
    queries_this_week: int
    queries_last_week: int
    queries_two_weeks_ago: int
    days_since_signup: int
    features_used: List[str]
    avg_satisfaction: float

def get_user_cohort_v2(activity: UserActivity) -> str:
    """
    Classify user with context-aware logic.
    
    Cohorts:
    - new_power: <30 days old, >50 queries/week (onboarding burst)
    - sustained_power: >30 days old, >50 queries/week (true power user)
    - growing: Usage increasing week-over-week
    - at_risk: Usage declining >30% week-over-week
    - casual: <10 queries/week, satisfied (low but happy)
    - churning: <10 queries/week, unsatisfied (about to leave)
    """
    
    # Check account age
    is_new = activity.days_since_signup < 30
    
    # Check usage level
    is_high_usage = activity.queries_this_week > 50
    is_low_usage = activity.queries_this_week < 10
    
    # Check trend
    if activity.queries_last_week > 0:
        trend = (activity.queries_this_week - activity.queries_last_week) / activity.queries_last_week
    else:
        trend = 0
    
    is_growing = trend > 0.2  # 20% increase
    is_declining = trend < -0.3  # 30% decrease
    
    # Classify with context
    if is_high_usage and is_new:
        return "new_power"  # Might churn after onboarding
    elif is_high_usage and not is_new:
        return "sustained_power"  # True power user, retain at all costs
    elif is_growing:
        return "growing"  # Positive momentum, nurture
    elif is_declining and not is_low_usage:
        return "at_risk"  # Intervention needed
    elif is_low_usage and activity.avg_satisfaction >= 4.0:
        return "casual"  # Low usage but happy, don't bother
    elif is_low_usage and activity.avg_satisfaction < 3.0:
        return "churning"  # About to leave, re-engage or let go
    else:
        return "normal"  # Default bucket

# Use this in metric recording
cohort = get_user_cohort_v2(user_activity)
cohort_queries.labels(cohort=cohort, feature_used=feature).inc()
```

**How to verify the fix:**

[TERMINAL]
```bash
# Export cohort sizes and check for sanity
curl -s http://localhost:9090/api/v1/query?query='sum(rag_cohort_active_users)%20by%20(cohort)' | jq

# Expected output (should make intuitive sense):
# {"cohort": "sustained_power", "value": 120}   # 12% of 1000 users
# {"cohort": "new_power", "value": 80}          # 8% (onboarding burst)
# {"cohort": "growing", "value": 150}           # 15%
# {"cohort": "casual", "value": 400}            # 40% (largest group)
# {"cohort": "at_risk", "value": 100}           # 10%
# {"cohort": "churning", "value": 50}           # 5%

# Verify retention by cohort (should be different)
# Sustained power: 85%+ retention
# New power: 30-50% retention (some churn after onboarding)
# Growing: 70%+ retention
# At-risk: 40-60% retention
```

**How to prevent:**
- ✅ Use multiple signals for cohort classification (usage, trend, satisfaction, features)
- ✅ Validate cohort definitions with real user behavior data
- ✅ Review cohort sizes monthly (should match intuition: most users casual, few power)
- ✅ A/B test cohort interventions to verify definitions matter

**When this happens:**
Month 1-2 after launching cohort tracking. Executive asks 'Why is power user retention so low?' and you realize your definition is wrong.

---

#### Failure #4: Missing Critical Business Metrics (Blind Spots)

**[44:00] You instrumented dozens of metrics but missed the one that matters:**

[CODE: "incomplete_instrumentation.py"]
```python
# ❌ BAD: Only tracking what's easy to measure

# You tracked:
query_latency = Histogram('rag_query_latency_seconds', 'Latency')
query_counter = Counter('rag_queries_total', 'Total queries')
cache_hits = Counter('rag_cache_hits_total', 'Cache hits')
token_usage = Counter('rag_tokens_used_total', 'Tokens used')

# But you DIDN'T track:
# ❌ User satisfaction per query (the most important signal!)
# ❌ Revenue attribution (which queries led to upgrades?)
# ❌ Cost per cohort (are power users profitable?)
# ❌ Feature abandonment (users try feature once, never again)

# Result: You can optimize latency to 100ms but don't know if users are happy
```

**Error message you'll see:**

[EMAIL FROM EXECUTIVE]
```
From: CEO
Subject: Why is churn up 15% this month?

Looking at our dashboards, everything looks great:
- P95 latency: 234ms (down from 280ms last month) ✅
- Error rate: 0.3% (best ever) ✅  
- Cache hit rate: 87% (up from 82%) ✅

But churn is up 15% and revenue is flat.

What's going wrong? Why aren't the dashboards showing this?
```

**What this means:**
You optimized technical metrics (latency, errors) but didn't track business outcomes (satisfaction, churn predictors, revenue impact). Technical perfection doesn't guarantee business success.

Classic blind spots:
- **User satisfaction:** Never asked users if they're happy with answers
- **Feature value:** Don't know which features users find valuable
- **Cost efficiency:** Can't identify unprofitable user segments
- **Churn predictors:** No early warning signals

**How to fix it:**

[CODE: "complete_instrumentation.py"]
```python
# ✅ GOOD: Instrument business outcomes, not just technical metrics

# 1. User satisfaction (CRITICAL - ask users!)
satisfaction_rating = Histogram(
    'rag_satisfaction_rating',
    'User rating (1-5) after each query',
    ['user_cohort'],
    buckets=[1, 2, 3, 4, 5]
)

# 2. Feature value (which features drive retention?)
feature_value_score = Gauge(
    'rag_feature_value_score',
    'Calculated value score per feature (retention correlation)',
    ['feature']
)

# 3. Churn predictors (early warning)
user_engagement_trend = Gauge(
    'rag_user_engagement_trend',
    'Week-over-week engagement change (%)',
    ['user_cohort']
)

# 4. Revenue attribution (which queries led to revenue?)
revenue_attributed = Counter(
    'rag_revenue_attributed_usd',
    'Revenue attributed to RAG queries',
    ['user_cohort', 'feature_used']
)

# Implementation: Add feedback form after every query
@app.post("/api/query")
async def rag_query(query: str, user_id: str):
    # Execute query
    answer = execute_rag_query(query)
    
    # Return with feedback prompt
    return {
        "answer": answer,
        "feedback_form": {
            "question": "Was this answer helpful?",
            "options": ["👍 Yes", "👎 No", "⭐ Rate 1-5"]
        }
    }

@app.post("/api/feedback")
async def submit_feedback(
    query_id: str,
    user_id: str,
    rating: int,
    helpful: bool
):
    """Record user feedback"""
    cohort = get_user_cohort(user_id)
    
    # Record satisfaction
    satisfaction_rating.labels(user_cohort=cohort).observe(rating)
    
    # If user upgraded after using feature, attribute revenue
    if user_upgraded_recently(user_id):
        plan_price = get_user_plan_price(user_id)
        revenue_attributed.labels(
            user_cohort=cohort,
            feature_used=extract_feature_from_query(query_id)
        ).inc(plan_price)
```

**How to verify the fix:**

[TERMINAL]
```bash
# Check that satisfaction data is being collected
curl -s http://localhost:9090/api/v1/query?query='avg(rag_satisfaction_rating)' | jq '.data.result[0].value[1]'

# Should return number between 1-5
# If returns 0 or null → no feedback being collected!

# Check feedback collection rate
total_queries=$(curl -s 'http://localhost:9090/api/v1/query?query=sum(rag_queries_total)' | jq '.data.result[0].value[1]')
total_feedback=$(curl -s 'http://localhost:9090/api/v1/query?query=sum(rag_satisfaction_rating_count)' | jq '.data.result[0].value[1]')

feedback_rate=$(echo "scale=2; $total_feedback / $total_queries * 100" | bc)
echo "Feedback rate: $feedback_rate%"

# Goal: >20% feedback rate (1 in 5 queries rated)
# If <5% → users ignoring feedback form (make more prominent)
```

**How to prevent:**
- ✅ Start with business metrics, THEN add technical metrics
- ✅ For every technical metric, ask 'So what? Why does this matter to the business?'
- ✅ Monthly review: 'What question can't we answer with current dashboards?'
- ✅ Instrument feedback collection on day 1 (don't defer)

**When this happens:**
Month 2-3 in production. You have beautiful technical dashboards but can't explain why business metrics (churn, revenue) are declining.

---

#### Failure #5: KPI Calculation Errors (Wrong Aggregation Logic)

**[45:00] Your dashboard shows the wrong numbers:**

[CODE: "wrong_kpi_calc.py"]
```python
# ❌ BAD: Incorrect KPI calculation logic

def calculate_cost_per_user():
    """Calculate average cost per user - WRONG!"""
    
    # Query Prometheus for total cost (sum of all cohorts)
    total_cost = prom.custom_query(
        query='sum(rag_cohort_cost_usd)'
    )[0]['value'][1]
    
    # Query for active user count
    active_users = prom.custom_query(
        query='sum(rag_cohort_active_users)'
    )[0]['value'][1]
    
    # Calculate average
    cost_per_user = total_cost / active_users
    
    # ❌ PROBLEM: total_cost is COUNTER (cumulative since start)
    #            active_users is GAUGE (current snapshot)
    # You're dividing "total cost ever" by "users right now"
    # Result: cost_per_user = $15,000 / 500 users = $30/user
    # But this includes costs from 3 months ago!
    
    return cost_per_user
```

**Error message you'll see:**

[DASHBOARD: Nonsensical numbers]
```
Executive Dashboard shows:
- Cost per user: $127.45  
  (Actual: Should be ~$2-5/user/month)

- ROAI (Return on AI Investment): 0.08
  (Actual: Should be 1.5-3.0 for healthy business)

CEO asks: "Are we losing $127 per user?!"
You realize: Wrong calculation—using cumulative cost, not period cost
```

**What this means:**
You mixed metric types in calculations:
- **Counter:** Cumulative total (always increasing)
- **Gauge:** Current value (goes up and down)
- **Histogram:** Distribution of values

When calculating ratios/averages, you must use `rate()` or `increase()` to get period-specific values from counters.

**How to fix it:**

[CODE: "correct_kpi_calc.py"]
```python
# ✅ GOOD: Correct KPI calculation

def calculate_cost_per_user_correct():
    """Calculate average cost per user - CORRECT"""
    
    # Use rate() to get cost PER SECOND, multiply by period
    cost_last_24h = prom.custom_query(
        query='sum(rate(rag_cohort_cost_usd[24h])) * 86400'
        #          ^^^^                                ^^^^
        #          Get rate per second                Convert to 24h total
    )[0]['value'][1]
    
    # Active users is gauge, use directly
    active_users_current = prom.custom_query(
        query='sum(rag_cohort_active_users)'
    )[0]['value'][1]
    
    # Now calculation is correct: cost in last 24h / current users
    cost_per_user_daily = cost_last_24h / active_users_current
    
    # ✅ Result: $2.34/user/day (reasonable!)
    
    return cost_per_user_daily

def calculate_roai_correct():
    """Calculate Return on AI Investment - CORRECT"""
    
    # Revenue in last 30 days (from counter)
    revenue_30d = prom.custom_query(
        query='sum(increase(rag_revenue_attributed_usd[30d]))'
        #          ^^^^^^^^
        #          Use increase() for period total
    )[0]['value'][1]
    
    # AI costs in last 30 days (from counter)
    ai_costs_30d = prom.custom_query(
        query='''
            sum(increase(rag_cohort_cost_usd[30d]))
        '''
    )[0]['value'][1]
    
    # Calculate ROAI
    if ai_costs_30d > 0:
        roai = revenue_30d / ai_costs_30d
    else:
        roai = 0
    
    # ✅ Result: ROAI = 2.3 (earning $2.30 for every $1 spent on AI)
    
    return roai
```

**PromQL cheat sheet for KPI calculations:**

```promql
# For COUNTERS (cumulative totals):
increase(metric[5m])      # Total increase in last 5 minutes
rate(metric[5m])          # Per-second rate in last 5 minutes
rate(metric[5m]) * 300    # Total in last 5 minutes (rate × seconds)

# For GAUGES (current values):
metric                    # Use directly (no rate/increase)
avg_over_time(metric[1h]) # Average value in last hour

# For HISTOGRAMS:
histogram_quantile(0.95, rate(metric_bucket[5m]))  # P95 value
```

**How to verify the fix:**

[TERMINAL]
```bash
# Test KPI calculations
python -c "
from prometheus_api_client import PrometheusConnect
prom = PrometheusConnect('http://localhost:9090')

# Check cost per user
cost_query = 'sum(rate(rag_cohort_cost_usd[24h]) * 86400) / sum(rag_cohort_active_users)'
result = prom.custom_query(cost_query)
print(f'Cost per user (24h): \${result[0][\"value\"][1]:.2f}')

# Should be $1-10/user/day (reasonable range)
# If >$50 → something wrong with calculation or usage
"

# Verify calculation logic by checking components
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(rag_cohort_cost_usd[24h])%20*%2086400)'
# Should return cost in last 24h (not cumulative total)

curl -s 'http://localhost:9090/api/v1/query?query=sum(rag_cohort_active_users)'
# Should return current user count
```

**How to prevent:**
- ✅ Always use `rate()` or `increase()` with counters in calculations
- ✅ Test KPI calculations with known values (mock data where you know the answer)
- ✅ Validate KPIs against external source (compare to Stripe revenue, AWS costs)
- ✅ Document calculation logic in Grafana dashboard description

**When this happens:**
Week 2-4 after launching executive dashboard. Numbers look wrong, executives question the data, lose trust in dashboards.

---

**Summary of failures:**
1. Cardinality explosion → Use bounded labels
2. Dashboard timeouts → Use rate() with narrow windows, recording rules
3. Inaccurate cohorts → Multi-dimensional classification logic
4. Missing critical metrics → Start with business outcomes
5. Wrong KPI calculations → Use rate()/increase() for counters

Fix all five and your business metrics system will be production-ready."

---

## SECTION 9: PRODUCTION CONSIDERATIONS (3-4 minutes)

**[45:30-49:00] Running Business Metrics at Scale**

[SLIDE: "Production Considerations"]

**NARRATION:**
"Before you deploy this to production, here's what you need to know about running custom business metrics at scale.

### Scaling Concerns:

**At 1,000 queries/hour (small scale):**
- Performance: Metrics recording adds <5ms overhead per query (negligible)
- Cost: 
  - Prometheus: $20/month (1GB storage, single instance)
  - ClickHouse (optional): $50/month (8GB RAM instance)
  - Total: $70/month
- Monitoring: 
  - Check Prometheus cardinality daily
  - Review dashboard load times weekly
  - Verify feedback collection rate >20%

**At 10,000 queries/hour (medium scale):**
- Performance: 
  - Metrics overhead increases to 10-15ms per query
  - Background KPI calculation job takes 30-60 seconds (run every 5 minutes)
  - Grafana dashboard load time: 2-5 seconds
- Cost:
  - Prometheus: $80/month (HA setup, 2 instances, 20GB storage)
  - ClickHouse: $200/month (32GB RAM, better query performance)
  - Total: $280/month
- Required changes:
  - Enable Prometheus HA (2+ instances with deduplication)
  - Add recording rules for expensive queries
  - Use ClickHouse for cohort analysis (Prometheus becomes bottleneck)
  - Cache cohort lookups in Redis (don't query DB per request)

**At 100,000+ queries/hour (large scale):**
- Performance:
  - This approach starts to break—too much cardinality
  - Prometheus can't handle >1M active time series efficiently
  - Grafana queries timeout even with recording rules
- Cost:
  - Prometheus: $300-500/month (sharded setup, 100GB+ storage)
  - ClickHouse: $500-1000/month (64GB+ RAM cluster)
  - Total: $800-1500/month
- Recommendation: **Switch to BI tool + data warehouse** (Alternative 2)
  - Export metrics to BigQuery/Snowflake hourly
  - Use Looker/Tableau for executive dashboards
  - Keep Prometheus for technical metrics only
  - Saves engineering time fighting Prometheus at this scale

### Cost Breakdown (Monthly):

| Scale | Queries/Hour | Prometheus | ClickHouse | Engineering | Total |
|-------|--------------|------------|------------|-------------|-------|
| **Small** | 1K | $20 | $0 (optional) | 2 hrs/month | $70 |
| **Medium** | 10K | $80 | $200 | 4 hrs/month | $280 |
| **Large** | 100K+ | $300-500 | $500-1000 | 8+ hrs/month | $800-1500 |

**Cost optimization tips:**
1. **Reduce retention period:** Default 15 days → 7 days saves 50% storage costs
   ```yaml
   # prometheus.yml
   storage:
     tsdb:
       retention.time: 7d  # Down from 15d
   ```
   Estimated savings: $10-50/month depending on scale

2. **Use recording rules aggressively:** Pre-calculate expensive queries
   ```yaml
   # Recording rules reduce query time 10-100x
   # Example: rate(metric[5m]) calculated every 1m, cached
   ```
   Estimated savings: 2-4 hrs/month engineering time debugging slow queries

3. **Downsample historical data:** Keep 1-minute granularity for 7 days, 5-minute for 30 days
   - Requires Prometheus with Thanos or VictoriaMetrics
   Estimated savings: 60-70% storage costs for long retention

### Monitoring Requirements:

**Must track:**
- **Prometheus cardinality:** <10K time series for small, <100K for medium, <1M for large
  ```promql
  prometheus_tsdb_symbol_table_size_bytes
  ```
  Alert threshold: >1M time series
  
- **Dashboard load time:** P95 <5 seconds
  ```promql
  grafana_dashboard_load_duration_seconds{quantile="0.95"}
  ```
  Alert threshold: >10 seconds

- **Feedback collection rate:** >20% of queries should get user ratings
  ```promql
  sum(rate(rag_satisfaction_rating_count[5m])) 
  / 
  sum(rate(rag_queries_total[5m]))
  ```
  Alert threshold: <10% (users ignoring feedback forms)

**Alert on:**
- Cardinality explosion: `prometheus_tsdb_symbol_table_size_bytes > 1000000`
- Dashboard timeouts: `grafana_dashboard_load_duration_seconds{quantile="0.95"} > 10`
- Feedback drop-off: `feedback_collection_rate < 0.10`
- KPI calculation errors: `absent(rag_roai_ratio)` (metric missing = calculation failed)

**Example Prometheus alert rule:**
```yaml
# prometheus_alerts.yml

groups:
  - name: business_metrics_alerts
    rules:
      - alert: HighCardinality
        expr: prometheus_tsdb_symbol_table_size_bytes > 1000000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Prometheus cardinality too high"
          description: "Time series count: {{ $value }}. Check for unbounded labels."
      
      - alert: LowFeedbackRate
        expr: |
          sum(rate(rag_satisfaction_rating_count[10m])) 
          / 
          sum(rate(rag_queries_total[10m])) < 0.10
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "User feedback rate <10%"
          description: "Only {{ $value | humanizePercentage }} of queries are rated."
```

### Production Deployment Checklist:

Before going live:
- [ ] Verified all labels are bounded (<100 values per label)
- [ ] Tested dashboard queries with production traffic volume
- [ ] Set up recording rules for expensive queries
- [ ] Configured Prometheus alerts (cardinality, feedback rate, KPI errors)
- [ ] Documented cohort classification logic (so team can update it)
- [ ] Validated KPI calculations against external sources (Stripe, AWS bills)
- [ ] Created runbook for common failures (cardinality explosion, dashboard timeouts)
- [ ] Tested backup/restore of Prometheus data
- [ ] Set up monitoring for monitoring (Prometheus itself has metrics endpoint)

**Rollback plan:**
If business metrics cause production issues:
1. Disable metric recording (comment out recording calls)
2. Keep technical metrics from M2.3 (still have basic monitoring)
3. Investigate root cause (cardinality? query performance?)
4. Fix issue, re-enable gradually (10% → 50% → 100% traffic)

Your system now tracks business KPIs at production scale."

---

## SECTION 10: DECISION CARD (1-2 minutes) **[CRITICAL]**

**[49:00-50:30] Quick Reference Decision Guide**

[SLIDE: "Decision Card: Custom Business Metrics"]

**NARRATION:**
"Let me leave you with a decision card you can reference later.

**✅ BENEFIT:**
Track RAG-specific quality, cohorts, and revenue attribution using existing Prometheus infrastructure. Executives get business KPIs (satisfaction, ROAI, cohort retention) without $1000+/month analytics platform. Custom metrics + Grafana dashboards answer 'Are users happy?' and 'Which cohorts are profitable?'

**❌ LIMITATION:**
Requires 2-3 days instrumentation effort plus 2-4 hours/month maintenance. Prometheus struggles beyond 100K queries/hour—cardinality explodes, dashboards timeout, queries fail. Can't do funnel analysis or user journeys. At 1M+ time series, you'll need to migrate to BI platform + data warehouse ($1K-3K/month).

**💰 COST:**
Time to implement: 2-3 days initial setup (metric definitions, Grafana dashboards, KPI calculation jobs). Monthly cost at medium scale (10K queries/hour): $280 (Prometheus HA $80 + ClickHouse $200). Complexity: 300+ lines of instrumentation code, 5+ dashboards, background jobs for KPI calculation. Learning curve: 1-2 days to become proficient with PromQL and metric design patterns.

**🤔 USE WHEN:**
You have 1K-100K queries/month, need business visibility (satisfaction, cohorts, costs), already use Prometheus from M2.3, budget <$500/month for analytics, and can invest 2-3 days for setup. Your cohorts are simple (3-5 dimensions like free/paid/enterprise), executives want KPI dashboards updated every 5 minutes, and you don't need funnel analysis.

**🚫 AVOID WHEN:**
You have <100 users and no PMF yet (use Simple Daily Reports for $0/month), need funnel/journey analysis showing user paths (use Mixpanel $1K+/month instead), process >100K queries/hour—cardinality explodes (use BI tool + warehouse instead), have complex cohorts >10 dimensions (use Snowflake + Looker), or need real-time dashboards <1 second updates (use streaming pipeline with Kafka).

Save this card—you'll reference it when making architecture decisions."

---

## SECTION 11: PRACTATHON CHALLENGES (1-2 minutes)

**[50:30-52:00] Practice Challenges**

[SLIDE: "PractaThon Challenges"]

**NARRATION:**
"Time to practice. Choose your challenge level:

### 🟢 EASY (60 minutes)
**Goal:** Add basic satisfaction tracking to your RAG system

**Requirements:**
- Instrument your query endpoint to record satisfaction ratings (1-5 scale)
- Create Prometheus histogram metric for satisfaction by user cohort (free/paid)
- Build simple Grafana panel showing average satisfaction over last 7 days
- Test with 20 sample queries across both cohorts

**Starter code provided:**
- `satisfaction_metric_template.py` with metric definition skeleton
- `grafana_satisfaction_panel.json` with basic panel config

**Success criteria:**
- `/metrics` endpoint shows `rag_satisfaction_score` metric
- Grafana panel displays line graph of satisfaction by cohort
- Can observe different satisfaction levels between free vs. paid users

---

### 🟡 MEDIUM (90-120 minutes)
**Goal:** Implement full cohort tracking with retention analysis

**Requirements:**
- Classify users into 5 cohorts: new, casual, power, at_risk, churning
- Track queries, costs, and feature usage per cohort
- Calculate 7-day retention rate for each cohort
- Build Grafana dashboard with 4 panels: cohort sizes, costs per cohort, feature usage by cohort, retention rates
- Identify which cohort is most profitable (highest ROAI)

**Hints only:**
- Use multi-dimensional classification in `get_user_cohort()` (usage trend, account age, satisfaction)
- Calculate retention as: (users active today AND 7 days ago) / (users active 7 days ago)
- Track costs with labels: `cohort_cost.labels(cohort='power', cost_type='llm').inc(amount)`

**Success criteria:**
- Dashboard shows realistic cohort distribution (most users in casual/normal, few in power)
- Retention rates make intuitive sense (power users >80%, at-risk <50%)
- Can identify unprofitable cohort (cost > revenue attributed)
- **Bonus:** Alert fires when at-risk cohort size increases >20% week-over-week

---

### 🔴 HARD (4-5 hours)
**Goal:** Build complete executive analytics platform with KPI automation

**Requirements:**
- Implement all 4 metric categories: quality, cohorts, features, KPIs
- Create background job calculating 5 executive KPIs every 5 minutes: cost per user, ROAI, engagement score, NPS, hallucination rate
- Build executive dashboard with 8 panels answering: user satisfaction trend, cost efficiency by cohort, feature adoption rates, ROAI gauge with thresholds, retention comparison table, hallucination rate alert, revenue attribution breakdown, engagement score heatmap
- Write PromQL queries optimized for performance (use recording rules for expensive calculations)
- Handle cardinality properly (all labels bounded, <10K total time series)
- Set up 3 alerts: cardinality explosion, low feedback rate, ROAI drops below 1.0

**No starter code:**
- Design from scratch
- Meet production acceptance criteria

**Success criteria:**
- Dashboard loads in <3 seconds with 7 days of data
- All KPIs update every 5 minutes automatically
- Prometheus cardinality <5K time series (efficient metric design)
- Alerts trigger correctly in test scenarios
- **Bonus:** Export metrics to ClickHouse for cohort SQL queries, integrate with Stripe API for real revenue data, add A/B test tracking for feature experiments

---

**Submission:**
Push to GitHub with:
- Working code (instrumentation + KPI calculations)
- README explaining metric design decisions
- Screenshots of Grafana dashboards
- Test results showing acceptance criteria met
- (Optional) Loom video demonstrating dashboard and explaining cohort strategy

**Review:** Post in Discord #practathon channel for feedback from instructors and peers"

---

## SECTION 12: WRAP-UP & NEXT STEPS (1-2 minutes)

**[52:00-55:00] Summary**

[SLIDE: "What You Built Today"]

**NARRATION:**
"Let's recap what you accomplished:

**You built:**
- Custom Prometheus metrics tracking RAG quality (accuracy, satisfaction, hallucination rate) with bounded labels preventing cardinality explosion
- Cohort analysis system classifying users into meaningful segments (new, power, at-risk, casual, churning) with multi-dimensional logic
- Feature usage tracking identifying which RAG capabilities drive value vs. which are unused
- Executive KPI dashboard translating technical metrics into business language (ROAI, cost per user, engagement score, NPS)

**You learned:**
- ✅ How to design custom metrics that answer business questions executives actually ask
- ✅ Why cohort classification requires context (usage trend, account age, satisfaction) not just query count
- ✅ When product analytics platforms (Mixpanel) beat custom metrics and when simple reports are sufficient
- ✅ How to prevent metric cardinality explosion, dashboard timeouts, and inaccurate cohort definitions
- ✅ When NOT to use custom Prometheus metrics (<100 users or >100K queries/hour)

**Your system now:**
Has business intelligence layer ON TOP of technical monitoring from M2.3, M7.1, M7.2. You can answer executive questions: 'Are users satisfied?' (track satisfaction scores by cohort), 'Which features drive retention?' (feature usage correlated with retention rates), 'Is RAG profitable?' (ROAI showing revenue vs. AI costs), 'Which cohorts should we focus on?' (cost and revenue by segment)

This is what separates hobby projects from production SaaS businesses—measuring outcomes, not just outputs.

### Next Steps:

1. **Complete the PractaThon challenge** (choose your level: Easy 60 min, Medium 90-120 min, Hard 4-5 hours)
2. **Validate cohort definitions** with real user behavior (do they match intuition?)
3. **Set up executive dashboard review** (weekly 15-minute meeting to discuss KPIs)
4. **Join office hours** if you hit issues (Tuesday/Thursday 6 PM ET)
5. **Next video: M7.4 - Intelligent Alerting** (alert on anomalies, reduce alert fatigue, set up on-call rotation, automate incident response)

[SLIDE: "See You in M7.4: Intelligent Alerting"]

Great work today. You now have the business intelligence layer that executives need to make data-driven decisions. See you in the next video where we make alerting smarter!"

---

**END OF SCRIPT**

**Total Duration:** ~35 minutes  
**Word Count:** ~9,400 words  
**TVH Framework v2.0 Compliance:** ✅ All 12 sections complete

---

## PRODUCTION NOTES

**Visual Assets Needed:**
- Diagram: Business metrics vs. technical metrics flow
- Screenshot: Grafana executive dashboard (satisfaction, ROAI, cohorts)
- Code examples: All Python files provided
- Grafana JSON: Dashboard export for import

**Instructor Reminders:**
- Emphasize: This is optional—use M2.3 Prometheus only if sufficient
- Demo: Show cardinality explosion in real-time (create unbounded labels, watch Prometheus fail)
- Pause: After each failure scenario, let learners think about how they'd debug it

**Common Student Questions:**
Q: "Why not just use Google Analytics?"  
A: GA tracks web events (clicks, page views), not RAG quality metrics (accuracy, satisfaction with answers). Different use case.

Q: "Is ClickHouse required?"  
A: No. Use if >10K queries/month and need cohort SQL queries. Prometheus + Grafana handles most cases.

Q: "Can I track individual user sessions?"  
A: Not with Prometheus (aggregates data). Use Mixpanel/Amplitude for session tracking.

---
