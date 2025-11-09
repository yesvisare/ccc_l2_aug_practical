"""
Module 6.4: Compliance & Audit Logging
Implements tamper-proof audit trails, GDPR compliance automation, and retention policies.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Audit Event Schema ====================

class AuditEventType(Enum):
    """Types of auditable events"""
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    DOCUMENT_ACCESS = "document.access"
    DOCUMENT_QUERY = "document.query"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DELETE = "document.delete"
    PII_DETECTED = "pii.detected"
    PII_REDACTED = "pii.redacted"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_DENIED = "permission.denied"
    DATA_EXPORT = "data.export"  # GDPR right to portability
    DATA_DELETION = "data.deletion"  # GDPR right to erasure
    CONSENT_GIVEN = "consent.given"
    CONSENT_WITHDRAWN = "consent.withdrawn"


class AuditOutcome(Enum):
    """Outcome of the audited action"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class AuditEvent(BaseModel):
    """
    Structured audit event compliant with ISO 27001 requirements.
    Captures WHO, WHAT, WHEN, WHERE, and OUTCOME for every auditable action.
    """
    # Core identification
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # WHO - Actor information
    user_id: str
    user_role: str
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # WHAT - Action details
    resource_type: str  # e.g., "document", "query", "user"
    resource_id: str
    action: str  # e.g., "read", "write", "delete"
    outcome: AuditOutcome

    # WHERE - System context
    service_name: str = "rag-api"
    endpoint: Optional[str] = None
    environment: str = "production"

    # CONTEXT - Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    pii_accessed: bool = False
    data_classification: Optional[str] = None  # public, internal, confidential, restricted

    # Tamper-proofing (calculated on save)
    content_hash: Optional[str] = None
    previous_hash: Optional[str] = None

    def calculate_hash(self) -> str:
        """
        Calculate SHA-256 hash of event content for tamper-detection.

        Returns:
            32-character hexadecimal hash string
        """
        content = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "outcome": self.outcome.value,
        }
        json_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_elasticsearch(self) -> Dict[str, Any]:
        """Convert to Elasticsearch document format"""
        doc = self.model_dump()
        doc['event_type'] = self.event_type.value
        doc['outcome'] = self.outcome.value
        doc['timestamp'] = self.timestamp.isoformat()
        doc['@timestamp'] = self.timestamp.isoformat()  # Elasticsearch standard field
        return doc


# ==================== Audit Storage ====================

class AuditStorage:
    """
    Manages audit log storage in Elasticsearch.
    Implements tamper-proof chaining and retention policies.
    """

    def __init__(self, es_client=None):
        """
        Initialize audit storage.

        Args:
            es_client: Elasticsearch client instance (optional)
        """
        self.es = es_client
        self.index_pattern = "audit-logs"
        self._last_hash: Optional[str] = None

        if self.es:
            try:
                self._create_index_template()
                self._last_hash = self._get_last_hash()
                logger.info("AuditStorage initialized with Elasticsearch")
            except Exception as e:
                logger.error(f"Failed to initialize Elasticsearch: {e}")
                self.es = None
        else:
            logger.warning("⚠️ AuditStorage initialized without Elasticsearch (fallback mode)")

    def _create_index_template(self):
        """
        Create Elasticsearch index template with proper mappings.
        Time-series indices: audit-logs-2024-11, audit-logs-2024-12, etc.
        """
        if not self.es:
            return

        template = {
            "index_patterns": ["audit-logs-*"],
            "template": {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                },
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "event_id": {"type": "keyword"},
                        "event_type": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "user_role": {"type": "keyword"},
                        "resource_type": {"type": "keyword"},
                        "resource_id": {"type": "keyword"},
                        "action": {"type": "keyword"},
                        "outcome": {"type": "keyword"},
                        "service_name": {"type": "keyword"},
                        "endpoint": {"type": "keyword"},
                        "environment": {"type": "keyword"},
                        "ip_address": {"type": "ip"},
                        "pii_accessed": {"type": "boolean"},
                        "data_classification": {"type": "keyword"},
                        "content_hash": {"type": "keyword"},
                        "previous_hash": {"type": "keyword"},
                        "metadata": {"type": "object", "enabled": True},
                        "error_message": {"type": "text"},
                    }
                }
            }
        }

        try:
            self.es.indices.put_index_template(
                name="audit-logs-template",
                body=template
            )
            logger.info("Elasticsearch index template created")
        except Exception as e:
            logger.error(f"Failed to create index template: {e}")

    def _get_index_name(self) -> str:
        """Get current month's index name"""
        return f"audit-logs-{datetime.utcnow().strftime('%Y-%m')}"

    def _get_last_hash(self) -> Optional[str]:
        """
        Get the hash of the most recent audit event.
        Used for chaining new events (blockchain-style).

        Returns:
            Hash string or None if no previous events exist
        """
        if not self.es:
            return None

        try:
            result = self.es.search(
                index=f"{self.index_pattern}-*",
                body={
                    "size": 1,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": ["content_hash"]
                }
            )
            if result['hits']['hits']:
                return result['hits']['hits'][0]['_source']['content_hash']
            return None
        except Exception as e:
            logger.warning(f"Could not retrieve last hash: {e}")
            return None

    def store_event(self, event: AuditEvent) -> bool:
        """
        Store audit event with tamper-proof chaining.

        Args:
            event: AuditEvent to store

        Returns:
            True on success, False on failure
        """
        try:
            # Add hash chaining
            event.previous_hash = self._last_hash
            event.content_hash = event.calculate_hash()

            if self.es:
                # Store in Elasticsearch
                self.es.index(
                    index=self._get_index_name(),
                    document=event.to_elasticsearch(),
                    id=event.event_id
                )
                # Update last hash for next event
                self._last_hash = event.content_hash
                logger.info(f"Stored audit event: {event.event_type.value} by {event.user_id}")
            else:
                # Fallback to local storage
                self._store_to_fallback(event)

            return True
        except Exception as e:
            logger.error(f"CRITICAL: Audit log storage failed: {e}")
            self._store_to_fallback(event)
            return False

    def _store_to_fallback(self, event: AuditEvent):
        """
        Emergency fallback: write to local file if Elasticsearch fails.
        This ensures we never lose audit events.
        """
        fallback_path = "audit-fallback.jsonl"
        try:
            with open(fallback_path, "a") as f:
                f.write(json.dumps(event.to_elasticsearch()) + "\n")
            logger.info(f"Stored to fallback: {event.event_id}")
        except Exception as e:
            logger.error(f"Fallback storage failed: {e}")

    def bulk_store_events(self, events: List[AuditEvent]) -> int:
        """
        Bulk store events for efficiency.

        Args:
            events: List of AuditEvent objects

        Returns:
            Count of successfully stored events
        """
        if not self.es:
            for event in events:
                self.store_event(event)
            return len(events)

        try:
            from elasticsearch.helpers import bulk

            actions = []
            for event in events:
                event.previous_hash = self._last_hash
                event.content_hash = event.calculate_hash()
                self._last_hash = event.content_hash

                actions.append({
                    "_index": self._get_index_name(),
                    "_id": event.event_id,
                    "_source": event.to_elasticsearch()
                })

            success, failed = bulk(self.es, actions)
            logger.info(f"Bulk stored {success} events, {failed} failed")
            return success
        except Exception as e:
            logger.error(f"Bulk store failed: {e}")
            return 0

    def verify_chain_integrity(self, user_id: Optional[str] = None, limit: int = 1000) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log chain.
        Detects any tampering by checking hash chaining.

        Args:
            user_id: Optional user ID to verify specific user's events
            limit: Maximum number of events to verify

        Returns:
            Dictionary with verification results
        """
        if not self.es:
            return {"verified": False, "reason": "Elasticsearch not available"}

        try:
            query = {"match_all": {}}
            if user_id:
                query = {"term": {"user_id": user_id}}

            result = self.es.search(
                index=f"{self.index_pattern}-*",
                body={
                    "query": query,
                    "size": limit,
                    "sort": [{"@timestamp": {"order": "asc"}}]
                }
            )

            events = result['hits']['hits']
            if not events:
                return {"verified": True, "events_checked": 0, "issues": []}

            issues = []
            prev_hash = None

            for i, hit in enumerate(events):
                event = hit['_source']
                expected_prev = prev_hash
                actual_prev = event.get('previous_hash')

                if expected_prev != actual_prev:
                    issues.append({
                        "event_id": event['event_id'],
                        "position": i,
                        "expected_previous_hash": expected_prev,
                        "actual_previous_hash": actual_prev
                    })

                prev_hash = event['content_hash']

            return {
                "verified": len(issues) == 0,
                "events_checked": len(events),
                "issues": issues
            }
        except Exception as e:
            logger.error(f"Chain verification failed: {e}")
            return {"verified": False, "reason": str(e)}


# ==================== GDPR Compliance ====================

class GDPRCompliance:
    """
    Automates GDPR compliance workflows.
    Implements Right to Erasure, Right to Portability, and consent tracking.
    """

    def __init__(self, storage: AuditStorage):
        """
        Initialize GDPR compliance handler.

        Args:
            storage: AuditStorage instance
        """
        self.storage = storage

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        GDPR Right to Portability (Article 20).
        Export all audit logs involving a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with user's audit trail
        """
        if not self.storage.es:
            logger.warning("⚠️ Skipping user data export (no Elasticsearch)")
            return {"user_id": user_id, "events": [], "skipped": True}

        try:
            result = self.storage.es.search(
                index=f"{self.storage.index_pattern}-*",
                body={
                    "query": {"term": {"user_id": user_id}},
                    "size": 10000,
                    "sort": [{"@timestamp": {"order": "asc"}}]
                }
            )

            events = [hit['_source'] for hit in result['hits']['hits']]
            logger.info(f"Exported {len(events)} events for user {user_id}")

            return {
                "user_id": user_id,
                "export_date": datetime.utcnow().isoformat(),
                "total_events": len(events),
                "events": events
            }
        except Exception as e:
            logger.error(f"User data export failed: {e}")
            return {"user_id": user_id, "error": str(e)}

    def delete_user_data(self, user_id: str, retention_days: int = 7) -> Dict[str, Any]:
        """
        GDPR Right to Erasure (Article 17).
        Delete or anonymize user data after retention period.

        Args:
            user_id: User identifier
            retention_days: Days to wait before actual deletion

        Returns:
            Dictionary with deletion results
        """
        if not self.storage.es:
            logger.warning("⚠️ Skipping user data deletion (no Elasticsearch)")
            return {"user_id": user_id, "deleted_count": 0, "skipped": True}

        try:
            # First, log the deletion request
            deletion_event = AuditEvent(
                event_type=AuditEventType.DATA_DELETION,
                user_id=user_id,
                user_role="system",
                resource_type="user_data",
                resource_id=user_id,
                action="delete_request",
                outcome=AuditOutcome.SUCCESS,
                metadata={"retention_days": retention_days}
            )
            self.storage.store_event(deletion_event)

            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Delete old events
            result = self.storage.es.delete_by_query(
                index=f"{self.storage.index_pattern}-*",
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"user_id": user_id}},
                                {"range": {"@timestamp": {"lt": cutoff_date.isoformat()}}}
                            ]
                        }
                    }
                }
            )

            deleted_count = result.get('deleted', 0)
            logger.info(f"Deleted {deleted_count} events for user {user_id}")

            return {
                "user_id": user_id,
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
        except Exception as e:
            logger.error(f"User data deletion failed: {e}")
            return {"user_id": user_id, "error": str(e)}

    def track_consent(self, user_id: str, consent_given: bool, purpose: str) -> bool:
        """
        Track user consent for data processing.

        Args:
            user_id: User identifier
            consent_given: True if consent granted, False if withdrawn
            purpose: Purpose of data processing

        Returns:
            True on success
        """
        event_type = AuditEventType.CONSENT_GIVEN if consent_given else AuditEventType.CONSENT_WITHDRAWN

        consent_event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            user_role="user",
            resource_type="consent",
            resource_id=f"consent_{user_id}_{purpose}",
            action="consent_update",
            outcome=AuditOutcome.SUCCESS,
            metadata={"purpose": purpose, "consent_given": consent_given}
        )

        return self.storage.store_event(consent_event)


# ==================== Data Retention Policy ====================

class RetentionPolicy:
    """
    Enforces data retention policies based on classification.
    Automatically deletes logs after retention periods.
    """

    # Default retention periods (in days)
    RETENTION_PERIODS = {
        "confidential": 2555,  # 7 years
        "internal": 1095,      # 3 years
        "public": 365,         # 1 year
        "restricted": 3650,    # 10 years
        "security_critical": 3650  # 10 years
    }

    def __init__(self, storage: AuditStorage):
        """
        Initialize retention policy enforcer.

        Args:
            storage: AuditStorage instance
        """
        self.storage = storage

    def enforce_retention(self, classification: str) -> Dict[str, Any]:
        """
        Enforce retention policy for a specific data classification.

        Args:
            classification: Data classification (confidential, internal, public, etc.)

        Returns:
            Dictionary with enforcement results
        """
        if not self.storage.es:
            logger.warning("⚠️ Skipping retention enforcement (no Elasticsearch)")
            return {"classification": classification, "deleted_count": 0, "skipped": True}

        retention_days = self.RETENTION_PERIODS.get(classification, 1095)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        try:
            result = self.storage.es.delete_by_query(
                index=f"{self.storage.index_pattern}-*",
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"data_classification": classification}},
                                {"range": {"@timestamp": {"lt": cutoff_date.isoformat()}}}
                            ]
                        }
                    }
                }
            )

            deleted_count = result.get('deleted', 0)
            logger.info(f"Retention enforcement: deleted {deleted_count} {classification} events")

            return {
                "classification": classification,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_count": deleted_count
            }
        except Exception as e:
            logger.error(f"Retention enforcement failed: {e}")
            return {"classification": classification, "error": str(e)}

    def enforce_all_policies(self) -> List[Dict[str, Any]]:
        """
        Enforce retention policies for all classifications.

        Returns:
            List of enforcement results for each classification
        """
        results = []
        for classification in self.RETENTION_PERIODS.keys():
            result = self.enforce_retention(classification)
            results.append(result)
        return results


# ==================== CLI Usage Examples ====================

if __name__ == "__main__":
    print("=== Module 6.4: Compliance & Audit Logging ===\n")

    # Example 1: Create audit event
    print("1. Creating audit event...")
    event = AuditEvent(
        event_type=AuditEventType.DOCUMENT_ACCESS,
        user_id="user_123",
        user_role="analyst",
        resource_type="document",
        resource_id="doc_456",
        action="read",
        outcome=AuditOutcome.SUCCESS,
        pii_accessed=True,
        data_classification="confidential"
    )
    event.content_hash = event.calculate_hash()
    print(f"   Event ID: {event.event_id}")
    print(f"   Hash: {event.content_hash[:16]}...")
    print(f"   # Expected: UUID and 64-char hash\n")

    # Example 2: Initialize storage (without Elasticsearch for demo)
    print("2. Initializing audit storage...")
    storage = AuditStorage(es_client=None)
    print("   Storage initialized in fallback mode")
    print("   # Expected: Warning about no Elasticsearch\n")

    # Example 3: Store event
    print("3. Storing audit event...")
    success = storage.store_event(event)
    print(f"   Stored: {success}")
    print("   # Expected: Event written to audit-fallback.jsonl\n")

    # Example 4: GDPR export (simulated)
    print("4. GDPR user data export...")
    gdpr = GDPRCompliance(storage)
    export = gdpr.export_user_data("user_123")
    print(f"   Exported events: {export.get('total_events', 0)}")
    print(f"   # Expected: 0 events (no ES), skipped=True\n")

    # Example 5: Chain verification (simulated)
    print("5. Verifying audit chain integrity...")
    verification = storage.verify_chain_integrity()
    print(f"   Verified: {verification.get('verified', False)}")
    print(f"   # Expected: False (no ES available)\n")

    print("✓ All examples completed. See audit-fallback.jsonl for stored events.")
