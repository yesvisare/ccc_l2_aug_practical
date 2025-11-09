# Module 6.3: RBAC & Multi-Level Access Control

Enterprise role-based access control (RBAC) implementation for RAG systems with document-level filtering, audit logging, and compliance support.

## Overview

This module implements a production-ready RBAC system with:
- **Three-tier role hierarchy** (admin > editor > viewer)
- **PostgreSQL-backed persistence** with connection pooling
- **Casbin policy enforcement** for flexible permission rules
- **Document-level access control** via Pinecone metadata filtering
- **Comprehensive audit logging** for compliance (SOC2, ISO27001)
- **<100ms permission check overhead**

**Scale**: 10-5,000 users | **Cost**: $100-400/month infrastructure | **Implementation**: 8-12 hours

---

## 🎯 Purpose

This module demonstrates how to enforce role and permission boundaries in production RAG systems through centralized authorization. You'll implement a policy-driven access control layer that gates document queries based on user roles, enforcing least-privilege principles. The system ensures that viewers can only read public documents, editors can modify internal content, and admins have full access to confidential data—all with comprehensive audit trails for compliance.

## 📚 Concepts Covered

- **Role-to-Permission Mapping**: Three-tier hierarchy (admin → editor → viewer) with inheritance
- **Resource/Action Model**: Declarative policy defining who can perform what actions on which resources
- **Policy Evaluation**: Casbin-based enforcement with <100ms overhead per authorization check
- **FastAPI Dependency Injection**: `get_current_user` dependency resolving authenticated user context
- **Deny-by-Default**: All actions forbidden unless explicitly allowed by policy
- **Audit Hooks**: Permission check logging for compliance reporting (SOC2, ISO27001)
- **Demo Mode**: File-based users and policies for offline development without external IdP

## ✅ After Completing This Module

- Define and load RBAC policies (roles, permissions, hierarchies)
- Protect API endpoints with permission checks using FastAPI dependencies
- Write and verify authorization tests covering all permission scenarios
- Operate entirely offline with file-based user store and policy configuration
- Understand when RBAC suffices vs. when ABAC or managed identity is needed

## 🗺️ Context in Learning Track

**Module 6: Enterprise Security & Compliance**

This module sits between:
- **M6.2 (Secrets Management)**: Protects database credentials used by RBAC system
- **M6.4 (Compliance & Auditing)**: Consumes permission logs for compliance dashboards

RBAC gates all document index and query operations, ensuring users only access data matching their clearance level. Documents with PII detected in M6.1 are automatically marked confidential, restricting access to admins only.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database and Pinecone credentials
```

### 3. Run the Demo

**Windows (PowerShell - Recommended):**
```powershell
# Run API server
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; uvicorn app:app --reload"

# Run demo script
./scripts/run_demo.ps1

# Run tests
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; pytest -q"
```

**Linux/Mac (Bash):**
```bash
# Run API server
./scripts/run_api.sh

# Run demo script
./scripts/run_demo.sh

# Run tests
PYTHONPATH=$PWD/src:$PWD pytest -q
```

**Jupyter Notebook:**
```bash
jupyter notebook notebooks/L2_M6_RBAC_Multi-Level_Access.ipynb
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Health Check │  │ User Mgmt    │  │ Query Docs   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │ RBAC Manager   │                        │
│                    │ (Casbin)       │                        │
│                    └───────┬────────┘                        │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐              │
│         │                  │                  │              │
│    ┌────▼─────┐    ┌──────▼──────┐    ┌─────▼──────┐       │
│    │PostgreSQL│    │Redis Cache  │    │Pinecone    │       │
│    │(Users,   │    │(Permissions)│    │(Filtered   │       │
│    │ Roles,   │    │             │    │ Queries)   │       │
│    │ Logs)    │    │             │    │            │       │
│    └──────────┘    └─────────────┘    └────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Role Hierarchy

```python
admin > editor > viewer
```

- **Viewer**: Read public documents
- **Editor**: Read/write public + internal documents (inherits viewer)
- **Admin**: Full access including confidential documents (inherits editor)

### 2. Document Access Levels

| Access Level | Viewer | Editor | Admin |
|--------------|--------|--------|-------|
| Public       | ✓      | ✓      | ✓     |
| Internal     | ✗      | ✓      | ✓     |
| Confidential | ✗      | ✗      | ✓     |

### 3. Permission Check Flow

```python
1. Client sends request with X-API-Key header
2. Server looks up user by hashed API key
3. RBAC Manager checks user's roles against required permission
4. Permission check logged to database (audit trail)
5. Result cached in Redis (5-minute TTL)
6. Response returned with 200 (allowed) or 403 (denied)
```

### 4. Pinecone Filtering

Documents indexed with `access_level` metadata:

```python
{
    "id": "doc_123",
    "text": "Confidential salary data...",
    "metadata": {
        "access_level": "confidential"  # public | internal | confidential
    }
}
```

Queries automatically filtered based on user role:

```python
# Viewer query
filter = {"access_level": {"$in": ["public"]}}

# Editor query
filter = {"access_level": {"$in": ["public", "internal"]}}

# Admin query
filter = {"access_level": {"$in": ["public", "internal", "confidential"]}}
```

## Common Failures & Fixes

### 1. Permission Escalation via Unprotected Endpoints

**Symptom**: Any user can assign themselves admin role

**Root Cause**: Role management endpoints lack authorization checks

**Fix**:
```python
# WRONG
@app.post("/users/roles/assign")
async def assign_role(assignment: RoleAssignment):
    return rbac.assign_role(assignment.username, assignment.role_name)

# CORRECT
@app.post("/users/roles/assign")
async def assign_role(
    assignment: RoleAssignment,
    current_user: User = Depends(require_permission("role", "manage"))
):
    return rbac.assign_role(assignment.username, assignment.role_name)
```

### 2. Pinecone Filter Bypass

**Symptom**: Viewers accessing confidential documents

**Root Cause**: Accepting client-provided filters instead of server-enforced

**Fix**:
```python
# WRONG
@app.post("/query")
async def query(req: QueryRequest):
    filter = req.access_levels  # Client-provided
    return pinecone_index.query(filter=filter)

# CORRECT
@app.post("/query")
async def query(req: QueryRequest, user: User = Depends(get_current_user)):
    filter = rbac.get_pinecone_filter(user)  # Server-generated
    return pinecone_index.query(filter=filter)
```

### 3. Circular Role Hierarchies

**Symptom**: Stack overflow during permission checks

**Root Cause**: Circular inheritance (e.g., admin → editor → manager → admin)

**Fix**:
```python
# Detect cycles before adding
cycles = rbac.detect_circular_roles()
if cycles:
    raise ValueError(f"Circular role hierarchy detected: {cycles}")
```

### 4. Permission Cache Staleness

**Symptom**: User retains old permissions after role revocation

**Root Cause**: Cached permissions not invalidated on role change

**Fix**:
```python
def revoke_role(username: str, role_name: str):
    success = rbac.revoke_role(username, role_name)
    if success and redis_client:
        # Invalidate cached permissions
        redis_client.delete(f"permissions:{username}")
    return success
```

### 5. Database Connection Exhaustion

**Symptom**: "Too many connections" errors under load

**Root Cause**: Missing connection pooling or pool too small

**Fix**:
```python
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=50,        # Adjust based on load
    max_overflow=100,    # Allow bursts
    pool_pre_ping=True   # Verify connections
)
```

## Decision Card

### ✅ Use RBAC When:
- 10-5,000 users with varying access needs
- Handling confidential documents requiring access control
- Compliance requirements (SOC2, ISO27001, HIPAA)
- Budget allows $100+/month infrastructure
- Accept <100ms permission check overhead

### 🚫 Avoid RBAC When:
- <10 users with only two access tiers → Use boolean `is_admin` flag
- Complex conditional policies needed → Use ABAC (Attribute-Based Access Control)
- Need instant session-wide revocation → Use session invalidation
- >10,000 concurrent users → Use managed identity service (Auth0, Okta)
- Multi-tenant SaaS → Add tenant isolation layer first

## API Endpoints

### Health & Status

```bash
# Health check
curl http://localhost:8000/health

# Permission statistics (requires auth)
curl -H "X-API-Key: admin-key-123" http://localhost:8000/stats
```

### User Management (Admin Only)

```bash
# Create user
curl -X POST http://localhost:8000/users \
  -H "X-API-Key: admin-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "api_key": "newuser-key-abc",
    "roles": ["viewer"]
  }'

# Assign role
curl -X POST http://localhost:8000/users/roles/assign \
  -H "X-API-Key: admin-key-123" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "role_name": "editor"}'

# Revoke role
curl -X POST http://localhost:8000/users/roles/revoke \
  -H "X-API-Key: admin-key-123" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "role_name": "editor"}'
```

### Permission Checking

```bash
# Check specific permission
curl -X POST http://localhost:8000/permissions/check \
  -H "X-API-Key: viewer-key-789" \
  -H "Content-Type: application/json" \
  -d '{"resource": "document", "action": "write"}'

# Get accessible document levels
curl http://localhost:8000/permissions/accessible-levels \
  -H "X-API-Key: viewer-key-789"
```

### Document Queries

```bash
# Query documents (filtered by role)
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: viewer-key-789" \
  -H "Content-Type: application/json" \
  -d '{"query": "financial data", "top_k": 5}'
```

## Troubleshooting

### Database Connection Errors

```
Error: FATAL: too many connections
```

**Solution**: Increase connection pool size or enable connection pooling in config.

### Slow Permission Checks

```
Warning: Permission check took 150ms
```

**Solution**: Enable Redis caching with 5-minute TTL.

### 403 Errors After Role Change

```
Error: Permission denied despite role assignment
```

**Solution**: Clear cached permissions or wait for cache TTL expiration.

### Casbin Policy Not Loading

```
Error: Policy file not found
```

**Solution**: RBAC Manager creates default model automatically. Check `CASBIN_MODEL_PATH` in config.

## Performance Benchmarks

| Metric | Without Cache | With Redis |
|--------|--------------|------------|
| Permission check latency (P50) | 35ms | 5ms |
| Permission check latency (P95) | 80ms | 15ms |
| Database queries per check | 2-3 | 0 (cached) |
| Max throughput (req/s) | 500 | 5,000 |

## Production Deployment

### Required Infrastructure

1. **PostgreSQL 15+**: $50-100/month (managed service)
2. **Redis 6+**: $30-50/month (optional but recommended)
3. **Monitoring**: $20/month (Prometheus + Grafana)

### Pre-Deployment Checklist

- [ ] Database indexes on `api_key_hash`, `timestamp`
- [ ] Connection pool configured (50-100 connections)
- [ ] Redis caching enabled with TTL
- [ ] Rate limiting on admin endpoints
- [ ] Monitoring alerts configured
- [ ] Log retention policy documented
- [ ] Security audit completed

### Environment Variables

Configuration via `.env` file (copy from `.env.example`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string for user/role persistence | `postgresql://localhost:5432/rbac_db` |
| `PINECONE_API_KEY` | Pinecone API key for document-level filtering | (none - optional) |
| `PINECONE_ENVIRONMENT` | Pinecone environment/region | (none - optional) |
| `PINECONE_INDEX_NAME` | Target index for RBAC-filtered queries | `rbac-docs` |
| `REDIS_HOST` | Redis host for permission caching | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Redis database number | `0` |
| `CASBIN_MODEL_PATH` | Path to Casbin RBAC model file (auto-created if omitted) | (auto-generated) |
| `PERMISSION_CACHE_TTL` | Seconds to cache permission decisions | `300` (5 min) |
| `API_HOST` | API server bind address | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |
| `ENABLE_METRICS` | Enable Prometheus metrics endpoint | `false` |
| `LOG_LEVEL` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) | `INFO` |

**Demo Mode (No External Dependencies):**

For local development/testing without PostgreSQL or Pinecone:
- Uses SQLite in-memory database (no DATABASE_URL needed)
- File-based user management via `example_data.json`
- No external IdP/JWT integration required
- Casbin policy auto-generated at runtime

To run in demo mode, simply omit DATABASE_URL or use `sqlite:///rbac_demo.db`.

## Testing

**Windows (PowerShell):**
```powershell
# Run all tests
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; pytest -q"

# Verbose output
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; pytest tests/ -v"

# Test coverage
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; pytest --cov=m6_rbac tests/"
```

**Linux/Mac (Bash):**
```bash
# Run all tests
PYTHONPATH=$PWD/src:$PWD pytest -q

# Verbose output
PYTHONPATH=$PWD/src:$PWD pytest tests/ -v

# Test coverage
PYTHONPATH=$PWD/src:$PWD pytest --cov=m6_rbac tests/
```

All tests run offline by default using SQLite and file-based user management.

## Integration with Other Modules

- **Module 6.1 (PII Detection)**: Documents with detected PII auto-marked as `confidential`
- **Module 6.2 (Secrets Management)**: Database credentials retrieved from vault
- **Module 6.4 (Compliance)**: Permission logs forwarded to Elasticsearch for audit reports

## Cost Breakdown

**Monthly operational costs at 1,000 requests/hour:**

| Component | Cost |
|-----------|------|
| PostgreSQL (managed) | $50-100 |
| Redis (optional) | $30-50 |
| Monitoring (Prometheus/Grafana) | $20 |
| **Total** | **$100-170** |

**One-time costs:**

| Activity | Time |
|----------|------|
| Initial implementation | 8-12 hours |
| Testing & deployment | 4-6 hours |
| Documentation | 2-3 hours |
| **Total** | **14-21 hours** |

## Next Module

**Module 6.4: Compliance & Auditing**
- Elasticsearch integration for permission logs
- Automated compliance reports
- Anomaly detection in access patterns
- Retention policies for audit data

## Resources

- [Casbin Documentation](https://casbin.org/)
- [PostgreSQL Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Pinecone Metadata Filtering](https://docs.pinecone.io/docs/metadata-filtering)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [SOC2 Compliance Guide](https://www.vanta.com/resources/soc-2-compliance-guide)

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
- Open an issue in the GitHub repository
- Review Module 6.3 video for detailed walkthrough
- Consult the Jupyter notebook for interactive examples
