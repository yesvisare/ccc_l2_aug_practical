"""
FastAPI entrypoint for Module 6.4: Compliance & Audit Logging
Provides REST API for audit logging, GDPR compliance, and retention management.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import module functions
from l2_m6_compliance_audit_logging import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditStorage,
    GDPRCompliance,
    RetentionPolicy,
)
from config import get_elasticsearch_client, config

# Configure logging
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M6.4 Compliance & Audit Logging API",
    description="Production-ready audit logging with GDPR compliance automation",
    version="1.0.0"
)

# Initialize storage and compliance handlers
es_client = get_elasticsearch_client()
audit_storage = AuditStorage(es_client=es_client)
gdpr_compliance = GDPRCompliance(audit_storage)
retention_policy = RetentionPolicy(audit_storage)


# ==================== Request/Response Models ====================

class AuditEventRequest(BaseModel):
    """Request model for creating audit events"""
    event_type: str
    user_id: str
    user_role: str
    resource_type: str
    resource_id: str
    action: str
    outcome: str = "success"
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    endpoint: Optional[str] = None
    pii_accessed: bool = False
    data_classification: Optional[str] = None
    metadata: Dict[str, Any] = {}


class GDPRExportRequest(BaseModel):
    """Request model for GDPR data export"""
    user_id: str


class GDPRDeleteRequest(BaseModel):
    """Request model for GDPR data deletion"""
    user_id: str
    retention_days: int = 7


class RetentionEnforcementRequest(BaseModel):
    """Request model for retention policy enforcement"""
    classification: Optional[str] = None  # If None, enforce all


# ==================== Health & Status ====================

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Status dictionary
    """
    return {
        "status": "ok",
        "service": "compliance-audit-logging",
        "elasticsearch": "connected" if es_client else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """
    Basic metrics endpoint (optional, for Prometheus).

    Returns:
        Metrics dictionary
    """
    if not es_client:
        return {
            "total_events": 0,
            "elasticsearch_available": False,
            "message": "Elasticsearch not available"
        }

    try:
        # Get count of all audit events
        result = es_client.count(index=f"{audit_storage.index_pattern}-*")
        total_events = result.get('count', 0)

        return {
            "total_events": total_events,
            "elasticsearch_available": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics fetch failed: {e}")
        return {
            "error": str(e),
            "elasticsearch_available": False
        }


# ==================== Audit Logging Endpoints ====================

@app.post("/audit/event")
async def create_audit_event(request: AuditEventRequest) -> Dict[str, Any]:
    """
    Create and store an audit event.

    Args:
        request: Audit event details

    Returns:
        Created event details
    """
    if not es_client:
        logger.warning("⚠️ Elasticsearch not available, using fallback storage")

    try:
        # Map string to enum
        event_type_enum = AuditEventType[request.event_type.upper().replace(".", "_")]
        outcome_enum = AuditOutcome[request.outcome.upper()]

        # Create audit event
        event = AuditEvent(
            event_type=event_type_enum,
            user_id=request.user_id,
            user_role=request.user_role,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            outcome=outcome_enum,
            session_id=request.session_id,
            ip_address=request.ip_address,
            endpoint=request.endpoint,
            pii_accessed=request.pii_accessed,
            data_classification=request.data_classification,
            metadata=request.metadata
        )

        # Store event
        success = audit_storage.store_event(event)

        return {
            "success": success,
            "event_id": event.event_id,
            "content_hash": event.content_hash,
            "skipped": not es_client,
            "reason": "no Elasticsearch connection" if not es_client else None
        }
    except Exception as e:
        logger.error(f"Failed to create audit event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/audit/verify")
async def verify_chain_integrity(user_id: Optional[str] = None, limit: int = 1000) -> Dict[str, Any]:
    """
    Verify audit log chain integrity.

    Args:
        user_id: Optional user ID to verify specific user's events
        limit: Maximum number of events to verify

    Returns:
        Verification results
    """
    if not es_client:
        return {
            "verified": False,
            "reason": "Elasticsearch not available",
            "skipped": True
        }

    result = audit_storage.verify_chain_integrity(user_id=user_id, limit=limit)
    return result


# ==================== GDPR Compliance Endpoints ====================

@app.post("/gdpr/export")
async def gdpr_export_user_data(request: GDPRExportRequest) -> Dict[str, Any]:
    """
    GDPR Right to Portability: Export all user audit data.

    Args:
        request: User ID to export

    Returns:
        User's complete audit trail
    """
    if not es_client:
        return {
            "user_id": request.user_id,
            "events": [],
            "skipped": True,
            "reason": "no Elasticsearch connection"
        }

    result = gdpr_compliance.export_user_data(request.user_id)
    return result


@app.post("/gdpr/delete")
async def gdpr_delete_user_data(request: GDPRDeleteRequest) -> Dict[str, Any]:
    """
    GDPR Right to Erasure: Delete user data after retention period.

    Args:
        request: User ID and retention days

    Returns:
        Deletion results
    """
    if not es_client:
        return {
            "user_id": request.user_id,
            "deleted_count": 0,
            "skipped": True,
            "reason": "no Elasticsearch connection"
        }

    result = gdpr_compliance.delete_user_data(
        user_id=request.user_id,
        retention_days=request.retention_days
    )
    return result


@app.post("/gdpr/consent/{user_id}")
async def track_consent(
    user_id: str,
    consent_given: bool,
    purpose: str
) -> Dict[str, Any]:
    """
    Track user consent for data processing.

    Args:
        user_id: User identifier
        consent_given: True if consent granted, False if withdrawn
        purpose: Purpose of data processing

    Returns:
        Success status
    """
    success = gdpr_compliance.track_consent(user_id, consent_given, purpose)

    return {
        "success": success,
        "user_id": user_id,
        "consent_given": consent_given,
        "purpose": purpose,
        "skipped": not es_client,
        "reason": "no Elasticsearch connection" if not es_client else None
    }


# ==================== Retention Policy Endpoints ====================

@app.post("/retention/enforce")
async def enforce_retention_policy(request: RetentionEnforcementRequest) -> Dict[str, Any]:
    """
    Enforce data retention policies.

    Args:
        request: Classification to enforce (or None for all)

    Returns:
        Enforcement results
    """
    if not es_client:
        return {
            "skipped": True,
            "reason": "no Elasticsearch connection",
            "results": []
        }

    if request.classification:
        result = retention_policy.enforce_retention(request.classification)
        return {"results": [result]}
    else:
        results = retention_policy.enforce_all_policies()
        return {"results": results}


# ==================== Local Development Runner ====================

if __name__ == "__main__":
    import uvicorn

    print("Starting Compliance & Audit Logging API...")
    print(f"Elasticsearch: {'Connected' if es_client else 'Not available (using fallback)'}")
    print("Access API docs at: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000)
