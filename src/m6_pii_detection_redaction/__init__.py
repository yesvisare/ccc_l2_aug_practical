"""
Module 6.1: PII Detection & Redaction
Public API exports.
"""

from .core import (
    PIIDetector,
    RedactionStrategy,
    PIIDetectionResult,
    PIIEntity,
    CustomRecognizerFactory,
    GDPRDeletionService,
    process_documents_parallel,
    create_whitelist_patterns,
    setup_logging,
    PIIMaskingFilter,
    PRESIDIO_AVAILABLE,
    # Simple API
    detect_pii,
    redact_text,
    load_policy,
    RedactionMode,
)

from .config import config, Config, get_clients, load_config

__all__ = [
    # Main classes
    "PIIDetector",
    "RedactionStrategy",
    "PIIDetectionResult",
    "PIIEntity",
    "CustomRecognizerFactory",
    "GDPRDeletionService",
    "PIIMaskingFilter",

    # Functions
    "process_documents_parallel",
    "create_whitelist_patterns",
    "setup_logging",

    # Simple API
    "detect_pii",
    "redact_text",
    "load_policy",
    "RedactionMode",

    # Configuration
    "config",
    "Config",
    "get_clients",
    "load_config",

    # Constants
    "PRESIDIO_AVAILABLE",
]
