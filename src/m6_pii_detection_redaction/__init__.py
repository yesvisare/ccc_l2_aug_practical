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
)

from .config import config, Config, get_clients

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

    # Configuration
    "config",
    "Config",
    "get_clients",

    # Constants
    "PRESIDIO_AVAILABLE",
]
