"""
Module 6.4: Compliance & Audit Logging
Production-ready audit trails with GDPR automation and retention policies.
"""

from m6_4_compliance_audit.core import (
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditStorage,
    GDPRCompliance,
    RetentionPolicy,
)
from m6_4_compliance_audit.config import (
    Config,
    config,
    get_elasticsearch_client,
    get_elasticsearch_config,
    is_elasticsearch_available,
)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditOutcome",
    "AuditStorage",
    "GDPRCompliance",
    "RetentionPolicy",
    "Config",
    "config",
    "get_elasticsearch_client",
    "get_elasticsearch_config",
    "is_elasticsearch_available",
]

__version__ = "1.0.0"
