"""
Smoke tests for Module 6.4: Compliance & Audit Logging
Tests basic functionality without requiring Elasticsearch.
"""

import pytest
import json
import os
from datetime import datetime

from l2_m6_compliance_audit_logging import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditStorage,
    GDPRCompliance,
    RetentionPolicy,
)
from config import Config


def test_config_loads():
    """Test that configuration loads without errors"""
    assert Config.ELASTICSEARCH_HOST is not None
    assert Config.AUDIT_BATCH_SIZE > 0
    assert Config.RETENTION_CONFIDENTIAL > 0


def test_audit_event_creation():
    """Test creating a basic audit event"""
    event = AuditEvent(
        event_type=AuditEventType.DOCUMENT_ACCESS,
        user_id="test_user",
        user_role="analyst",
        resource_type="document",
        resource_id="doc_123",
        action="read",
        outcome=AuditOutcome.SUCCESS
    )

    assert event.event_id is not None
    assert event.user_id == "test_user"
    assert event.event_type == AuditEventType.DOCUMENT_ACCESS
    assert event.outcome == AuditOutcome.SUCCESS


def test_audit_event_hash_calculation():
    """Test hash calculation for tamper detection"""
    event = AuditEvent(
        event_type=AuditEventType.USER_LOGIN,
        user_id="test_user",
        user_role="admin",
        resource_type="auth",
        resource_id="auth_system",
        action="login",
        outcome=AuditOutcome.SUCCESS
    )

    hash1 = event.calculate_hash()
    assert len(hash1) == 64  # SHA-256 produces 64-char hex string

    # Same event should produce same hash
    hash2 = event.calculate_hash()
    assert hash1 == hash2


def test_audit_event_to_elasticsearch():
    """Test conversion to Elasticsearch format"""
    event = AuditEvent(
        event_type=AuditEventType.DOCUMENT_QUERY,
        user_id="test_user",
        user_role="viewer",
        resource_type="document",
        resource_id="doc_456",
        action="query",
        outcome=AuditOutcome.SUCCESS,
        metadata={"query": "test query"}
    )

    es_doc = event.to_elasticsearch()

    assert "@timestamp" in es_doc
    assert es_doc["event_type"] == "document.query"
    assert es_doc["outcome"] == "success"
    assert es_doc["metadata"]["query"] == "test query"


def test_audit_storage_fallback():
    """Test audit storage with fallback (no Elasticsearch)"""
    # Remove fallback file if exists
    fallback_path = "audit-fallback.jsonl"
    if os.path.exists(fallback_path):
        os.remove(fallback_path)

    # Create storage without ES client
    storage = AuditStorage(es_client=None)

    # Store event
    event = AuditEvent(
        event_type=AuditEventType.USER_LOGOUT,
        user_id="test_user",
        user_role="admin",
        resource_type="auth",
        resource_id="auth_system",
        action="logout",
        outcome=AuditOutcome.SUCCESS
    )

    success = storage.store_event(event)
    assert success is True

    # Verify fallback file created
    assert os.path.exists(fallback_path)

    # Verify event in fallback file
    with open(fallback_path, "r") as f:
        lines = f.readlines()
        assert len(lines) > 0
        last_event = json.loads(lines[-1])
        assert last_event["user_id"] == "test_user"


def test_gdpr_export_without_es():
    """Test GDPR export gracefully handles missing Elasticsearch"""
    storage = AuditStorage(es_client=None)
    gdpr = GDPRCompliance(storage)

    result = gdpr.export_user_data("test_user")

    assert result["user_id"] == "test_user"
    assert result.get("skipped") is True
    assert result.get("events", []) == []


def test_gdpr_deletion_without_es():
    """Test GDPR deletion gracefully handles missing Elasticsearch"""
    storage = AuditStorage(es_client=None)
    gdpr = GDPRCompliance(storage)

    result = gdpr.delete_user_data("test_user", retention_days=7)

    assert result["user_id"] == "test_user"
    assert result.get("skipped") is True
    assert result.get("deleted_count") == 0


def test_retention_policy_periods():
    """Test retention policy has correct periods defined"""
    storage = AuditStorage(es_client=None)
    retention = RetentionPolicy(storage)

    assert "confidential" in retention.RETENTION_PERIODS
    assert "internal" in retention.RETENTION_PERIODS
    assert "public" in retention.RETENTION_PERIODS

    # Check 7 years for confidential
    assert retention.RETENTION_PERIODS["confidential"] == 2555
    # Check 3 years for internal
    assert retention.RETENTION_PERIODS["internal"] == 1095


def test_chain_verification_without_es():
    """Test chain verification gracefully handles missing Elasticsearch"""
    storage = AuditStorage(es_client=None)

    result = storage.verify_chain_integrity()

    assert result["verified"] is False
    assert "reason" in result


def test_example_data_exists():
    """Test that example data file exists and is valid"""
    assert os.path.exists("example_data.json")

    with open("example_data.json", "r") as f:
        data = json.load(f)

    assert "sample_audit_events" in data
    assert len(data["sample_audit_events"]) > 0

    # Verify first event has required fields
    first_event = data["sample_audit_events"][0]
    assert "event_id" in first_event
    assert "event_type" in first_event
    assert "user_id" in first_event
    assert "outcome" in first_event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
