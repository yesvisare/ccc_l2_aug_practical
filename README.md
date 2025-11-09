# Module 6.2: Secrets Management & Rotation

Enterprise-grade secrets management using HashiCorp Vault with zero-downtime key rotation, automated secret scanning, and multi-environment isolation.

## Overview

This module replaces insecure `.env` file secret management with centralized, auditable, auto-rotating credentials. It implements the complete secrets management system from Level 2, Module 6.2.

**What you'll learn:**
- Deploy HashiCorp Vault for centralized secrets management
- Implement zero-downtime key rotation without service interruption
- Scan codebase and git history for accidentally committed secrets
- Manage environment-specific secrets (dev/staging/prod) with proper isolation

---

## Learning Arc

### Purpose

This module teaches **enterprise-grade secrets management** to store API keys, database credentials, and tokens safely. Learn to implement **zero-downtime rotation** that swaps keys/tokens without dropping requests, minimizing blast radius when credentials leak. Move from risky `.env` files to centralized secret backends (HashiCorp Vault, AWS Secrets Manager, or file-based demo mode) with full audit trails and version control.

### Concepts Covered

- **Secret backends:** Start with env/file demo → optional cloud stores (Vault, AWS, GCP)
- **KMS & envelope encryption:** Protect secrets at rest with key encryption keys
- **Versioned secrets:** Track secret history, rollback to previous versions
- **Rotation policy:** Define interval (days), grace period (overlap), minimum overlap hours
- **Dry-run vs apply:** Test rotation logic without affecting production
- **Audit hooks:** Log all secret access for compliance (ties to M6.4)
- **Demo mode:** File-backed store + mock KMS for offline development (zero external calls)

### After Completing This Module

- Run a **dry-run rotation** to preview changes before applying
- Rotate a **demo secret** with zero downtime (no failed requests)
- Verify **consumers move to new versions** automatically
- Export a **rotation report** showing old→new mappings and timestamps
- Operate **offline** with file store + mock KMS (no cloud dependencies)

### Context in L2 Track

**Module 6: Enterprise Security & Compliance**
M6.2 Secrets Management sits between **M6.1 PII Detection** (data protection) and **M6.3 RBAC** (access control). Ties to **M6.4 Compliance Auditing** via audit hooks. Complements **M5 Index Operations** (safe storage of vector DB credentials) and **M7 Distributed Tracing** (secret-aware observability).

---

## Quickstart

### Prerequisites

- Docker (for Vault server)
- Python 3.9+
- Level 1 M3 completed (basic RAG system with .env configuration)

### Installation

```bash
# Clone repository
cd ccc_l2_aug_practical

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Start Vault Server (Development)

```bash
# Run Vault in dev mode (NOT for production!)
docker run -d --name vault-dev \
  -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=dev-root-token' \
  hashicorp/vault:latest

# Verify Vault is running
curl http://localhost:8200/v1/sys/health
```

### Configure Vault with Secrets

```bash
export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='dev-root-token'

# Enable key-value secrets engine
docker exec vault-dev vault secrets enable -version=2 -path=secret kv

# Create development secrets
docker exec vault-dev vault kv put secret/rag-system/dev \
  openai_key=sk-dev-test-key-12345 \
  pinecone_key=dev-pinecone-12345 \
  redis_url=redis://localhost:6379

# Verify secrets are stored
docker exec vault-dev vault kv get secret/rag-system/dev
```

### Run the Application

**Using provided scripts (recommended):**
```bash
# Windows (PowerShell)
powershell scripts/run_api.ps1

# Linux/Mac
bash scripts/run_api.sh
```

**Or manually:**
```bash
# Set environment
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=dev-root-token
export ENVIRONMENT=dev
export PYTHONPATH="$PWD/src:$PWD"

# Run FastAPI application
python app.py

# Or with uvicorn
uvicorn app:app --reload --port 8000
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "vault_connected": true,
#   "secrets_available": true,
#   "environment": "dev"
# }

# Query endpoint (demo)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Rotate key (admin endpoint)
curl -X POST http://localhost:8000/admin/rotate-key \
  -H "Content-Type: application/json" \
  -d '{"secret_key": "openai_key", "new_value": "sk-new-key-12345"}'
```

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Startup                       │
│  1. Load config from .env                                    │
│  2. Connect to Vault (with retry + fallback)                 │
│  3. Fetch secrets from Vault                                 │
│  4. Initialize OpenAI/Pinecone clients with secrets          │
│  5. Cache secrets in memory (5 min TTL)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Request Handling                          │
│  1. Track active requests (for rotation)                     │
│  2. Use cached secrets (no Vault call)                       │
│  3. Process request with OpenAI/Pinecone                     │
│  4. Return response                                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Secret Rotation                           │
│  1. Wait for active requests to complete (5s grace period)   │
│  2. Fetch new secret from Vault                              │
│  3. Verify new secret works (test API call)                  │
│  4. Update Vault with new secret                             │
│  5. Clear cache to force refetch                             │
│  6. Switch to new client                                     │
│  → ZERO DOWNTIME (no failed requests)                        │
└─────────────────────────────────────────────────────────────┘
```

## Common Failures & Fixes

### Failure 1: Rotation Race Condition

**Symptom:** `401 Unauthorized` errors during rotation

**Root Cause:** In-flight requests using old key after rotation completed

**Fix:**
```python
# Use request tracking with grace period
with rotation_manager.track_request():
    response = openai_client.chat.completions.create(...)
```

**Prevention:** Always use `SecretRotationManager.track_request()` context manager

### Failure 2: Vault Connection Failures

**Symptom:** `ConnectionRefusedError: Vault not accessible`

**Root Cause:** Vault server unavailable or token invalid

**Fix:**
```python
# Use ResilientVaultClient with fallback
vault_client = ResilientVaultClient(
    max_retries=3,
    fallback_env=True  # Falls back to .env if Vault down
)
```

**Prevention:**
- Monitor Vault health separately from application
- Implement retry logic with exponential backoff
- Have fallback to environment variables for graceful degradation

### Failure 3: Stale Secret Cache

**Symptom:** Services using old secrets after rotation

**Root Cause:** LRU cache not invalidated after rotation

**Fix:**
```python
# Clear cache after rotation
vault_client.rotate_secret("rag-system/prod", "openai_key", new_key)
vault_client.get_secret.cache_clear()  # Force refetch
```

**Prevention:**
- Call `cache_clear()` after every rotation
- Use cache versioning or pub/sub invalidation for distributed systems
- Reduce cache TTL to 60 seconds (trade-off: more Vault API calls)

### Failure 4: Secret Leaked to Git History

**Symptom:** Secret found in git history after file deletion

**Root Cause:** Git tracks all history permanently

**Fix:**
```bash
# Rewrite git history (DANGEROUS - requires force push)
git filter-repo --path .env --invert-paths
git push origin main --force

# Rotate leaked secret immediately
vault_client.rotate_secret("rag-system/prod", "leaked_key", new_value)
```

**Prevention:**
```bash
# Install pre-commit hooks
pip install pre-commit detect-secrets
pre-commit install

# Test it works
echo "VAULT_TOKEN=secret" > test.txt
git add test.txt
git commit -m "test"
# Should BLOCK with: "Detected secrets in test.txt"
```

### Failure 5: Environment Variable Conflicts

**Symptom:** Production using dev secrets

**Root Cause:** Local env vars shadowing deployment config

**Fix:**
```python
# Validate environment at startup
validate_environment_config("prod")
# Raises error if dev-root-token detected in production
```

**Prevention:**
- Explicit environment checks in AppConfig
- Separate Vault namespaces per environment
- Never share tokens across environments

## Decision Card

### ✅ BENEFIT

Centralized secrets management with zero-downtime rotation prevents the $15K leaked API key nightmare and eliminates manual key updates across 50 microservices. Audit logs prove who accessed production credentials for SOC2 compliance. Pre-commit hooks block 90% of accidental secret commits before they reach git.

### ❌ LIMITATION

Requires running and maintaining a Vault server (or paying $40-100/month for managed service), adding operational complexity with backups, upgrades, and HA configuration. OSS Vault becomes a performance bottleneck above 1000 concurrent connections, requiring migration to Vault Enterprise ($4.5K/year) or cloud secrets manager for large-scale deployments.

### 💰 COST

- **Time to implement:** 3-4 hours initial setup + 2 hours/month maintenance
- **Monthly cost at scale:**
  - Small (1 server): $20/month
  - Medium (5 services): $95/month
  - Large (15+ services): $320/month
- **Complexity:** 300+ lines of code, Vault server to operate, backup strategy, monitoring dashboards

### 🤔 USE WHEN

You have 10-500 secrets across multiple environments, need audit trails for compliance (SOC2/ISO27001), operate 5+ microservices requiring coordinated key rotation, or experienced a secret leak and can't risk it again. Budget $80-300/month for managed secrets infrastructure.

### 🚫 AVOID WHEN

- **Pre-revenue with <10 secrets:** Use .env files + git-secrets for $0/month
- **AWS-only infrastructure:** Use AWS Secrets Manager for native integrations
- **Edge compute with intermittent connectivity:** Use embedded HSM-backed secrets
- **>100 services needing 99.99% uptime:** Use Vault Enterprise or fully managed cloud service

## Alternative Solutions

### AWS Secrets Manager

**Best for:** Teams already on AWS wanting fully managed solution

**Trade-offs:**
- ✅ Zero infrastructure to manage, automatic rotation for AWS resources
- ❌ AWS vendor lock-in, higher cost at scale ($40/month for 100 secrets)

**Cost:** $0.40/secret/month + $0.05 per 10K retrievals

### Google Cloud Secret Manager

**Best for:** Teams on GCP needing automatic versioning

**Trade-offs:**
- ✅ Excellent versioning, free tier (6 secrets + 10K accesses/month)
- ❌ No automatic rotation (must build custom logic), GCP vendor lock-in

**Cost:** First 6 secrets free, then $0.06/secret/month

### Kubernetes Secrets

**Best for:** Teams already running Kubernetes

**Trade-offs:**
- ✅ Native K8s integration, no additional services to run
- ❌ Base64 is not encryption (must enable encryption at rest), no built-in rotation

**Cost:** Free (included in Kubernetes)

### .env Files

**Best for:** Solo developers, early-stage startups

**Trade-offs:**
- ✅ Zero infrastructure, zero cost, instant setup
- ❌ No audit trail, no rotation without downtime, high risk of git leaks

**Cost:** $0

### Decision Framework

| Criteria | Vault | AWS | GCP | K8s | .env |
|----------|-------|-----|-----|-----|------|
| Setup time | 2-3 hrs | 30 min | 30 min | 1 hr | 5 min |
| Monthly cost | $15-50 | $25-100 | $3-20 | $70+ | $0 |
| Best for # secrets | 10-500 | 10-100 | 10-200 | 50-1000 | 1-10 |
| Rotation downtime | 0 sec | 0 sec | 30 sec | 30 sec | 1-2 min |
| Multi-cloud | ✅ Yes | ❌ AWS only | ❌ GCP only | ✅ Yes | ✅ Yes |

## Environment Variables

All configuration is managed through environment variables (mirrored in `.env.example`):

### Core Configuration

- `ENVIRONMENT` - Environment name: `dev`, `staging`, or `prod` (default: `dev`)
- `SECRETS_BACKEND` - Secret store backend: `vault`, `aws`, `azure`, `gcp`, or `file` (default: `vault`)
- `SECRETS_FILE_PATH` - Path to secrets file when using file backend (default: `.secrets.json`)

### Vault Configuration

- `VAULT_ADDR` - Vault server URL (default: `http://localhost:8200`)
- `VAULT_TOKEN` - Vault authentication token (required for Vault backend)
- `VAULT_MOUNT_POINT` - Vault mount point for KV engine (default: `secret`)

### Rotation Policy

- `ROTATION_INTERVAL_DAYS` - Days between automatic rotations (default: `30`)
- `ROTATION_GRACE_DAYS` - Days of overlap when both old/new keys are valid (default: `1`)
- `MIN_OVERLAP_HOURS` - Minimum hours before old key expires after rotation (default: `24`)
- `ENABLE_ROTATION` - Enable automatic rotation: `true` or `false` (default: `true`)

### Encryption (KMS)

- `KMS_KEY_ID` - AWS KMS key ID or ARN (for AWS KMS envelope encryption)
- `AWS_REGION` - AWS region for KMS (default: `us-east-1`)
- `AZURE_KEY_VAULT_URL` - Azure Key Vault URL (for Azure Key Vault)
- `GCP_KMS_PROJECT_ID` - GCP project ID (for GCP Cloud KMS)

### Audit & Compliance

- `AUDIT_EMIT` - Enable audit logging: `true` or `false` (default: `true`, ties to M6.4)
- `AUDIT_BACKEND` - Audit log destination: `file`, `cloudwatch`, `datadog` (default: `file`)
- `AUDIT_FILE_PATH` - Path to audit log file (default: `logs/audit.log`)

### Feature Flags

- `FALLBACK_TO_ENV` - Fall back to .env if secret store unavailable (default: `true`)
- `ENABLE_METRICS` - Enable Prometheus metrics endpoint (default: `true`)
- `SECRET_CACHE_TTL` - Secret cache TTL in seconds (default: `300`)
- `SECRET_CACHE_MAXSIZE` - Max secrets in LRU cache (default: `128`)

### Demo Mode

When running without external dependencies (offline development):

```bash
# Windows (PowerShell)
$env:SECRETS_BACKEND = "file"
$env:SECRETS_FILE_PATH = ".secrets.json"
python app.py

# Linux/Mac
export SECRETS_BACKEND=file
export SECRETS_FILE_PATH=.secrets.json
python app.py
```

Demo mode uses file-backed storage with mock KMS (no network calls, no cloud credentials required).

## Production Deployment Checklist

Before going live:

- [ ] Vault running in HA mode (3 nodes) OR using managed service
- [ ] Automated backups configured (every 6 hours, retained 30 days)
- [ ] All secrets rotated from dev/staging (never reuse non-prod secrets in prod)
- [ ] Pre-commit hooks installed on all developer machines
- [ ] Monitoring dashboards created (Grafana/Datadog showing Vault health)
- [ ] Disaster recovery tested (restore from backup in <30 minutes)
- [ ] Fallback to environment variables implemented (graceful degradation)
- [ ] On-call runbook created (troubleshooting steps for Vault outages)
- [ ] Audit log retention configured (90 days for compliance)
- [ ] Access control tested (dev team can't access prod secrets)

## Troubleshooting

### Vault not starting

```bash
# Check if container is running
docker ps | grep vault

# View logs
docker logs vault-dev

# Restart container
docker restart vault-dev
```

### Authentication failed

```bash
# Verify token is correct
echo $VAULT_TOKEN

# Test authentication
curl -H "X-Vault-Token: $VAULT_TOKEN" \
  http://localhost:8200/v1/auth/token/lookup-self
```

### Secrets not found

```bash
# List all secrets
docker exec vault-dev vault kv list secret/

# Get specific secret
docker exec vault-dev vault kv get secret/rag-system/dev
```

### Application fails to start

```bash
# Check environment variables
env | grep VAULT

# Test Vault connectivity
curl http://localhost:8200/v1/sys/health

# Run with fallback enabled
export FALLBACK_TO_ENV=true
python app.py
```

## Running Tests

**Windows (PowerShell) - Quick Run:**
```powershell
powershell -c "$env:PYTHONPATH='$PWD/src;$PWD'; pytest -q"
```

**Linux/Mac - Quick Run:**
```bash
PYTHONPATH="$PWD/src:$PWD" pytest -q
```

**Detailed Test Commands:**
```bash
# Run smoke tests (verbose)
PYTHONPATH="$PWD/src:$PWD" pytest tests/test_smoke.py -v

# Run with coverage
PYTHONPATH="$PWD/src:$PWD" pytest tests/ --cov=m6_secrets --cov-report=html

# Run specific test
PYTHONPATH="$PWD/src:$PWD" pytest tests/test_smoke.py::TestVaultClient::test_vault_client_get_secret -v

# Windows equivalent (PowerShell)
$env:PYTHONPATH="$PWD/src;$PWD"; pytest tests/test_smoke.py -v
```

## Project Structure

```
├── src/
│   └── m6_secrets/                        # Main package
│       ├── __init__.py                    # Package exports
│       ├── core.py                        # Core module (VaultClient, rotation logic)
│       └── config.py                      # Configuration and environment validation
├── tests/
│   ├── __init__.py                        # Tests package
│   └── test_smoke.py                      # Smoke tests
├── scripts/
│   ├── run_api.ps1                        # Windows: Run FastAPI server
│   ├── run_api.sh                         # Linux/Mac: Run FastAPI server
│   ├── rotate_demo.ps1                    # Windows: Rotation demo
│   └── rotate_demo.sh                     # Linux/Mac: Rotation demo
├── notebooks/
│   └── L2_M6_Secrets_Management_Rotation.ipynb  # Jupyter notebook walkthrough
├── app.py                                 # FastAPI entrypoint (thin routing layer)
├── requirements.txt                       # Dependencies
├── .env.example                           # Environment template
├── example_data.json                      # Sample secrets and scenarios
└── README.md                              # This file
```

## Next Steps

1. **Complete PractaThon Challenge:**
   - 🟢 Easy (60 min): Basic Vault setup and secret scanning
   - 🟡 Medium (90-120 min): Zero-downtime rotation with metrics
   - 🔴 Hard (4-5 hrs): Production HA infrastructure with DR

2. **Deploy to Production:**
   - Migrate from dev mode Vault to production cluster
   - Configure automated backups
   - Set up monitoring and alerting
   - Implement disaster recovery

3. **Next Module: M6.3 RBAC & Multi-Level Access:**
   - Build role-based access control
   - Implement JWT permission claims
   - Pinecone metadata filtering for document-level access

## Resources

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [hvac Python Client](https://hvac.readthedocs.io/)
- [detect-secrets](https://github.com/Yelp/detect-secrets)
- [truffleHog](https://github.com/trufflesecurity/trufflehog)

## License

MIT

---

**Built with honesty.** This module teaches real production secrets management with actual trade-offs, costs, and limitations. No hype, just working code and honest guidance.
