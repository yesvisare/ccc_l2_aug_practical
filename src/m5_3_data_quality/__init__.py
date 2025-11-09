"""
M5.3: Data Quality & Validation Package

Production-ready data quality validation for RAG systems.
Provides chunk quality scoring, duplicate detection, and data drift monitoring.
"""

# Re-export core classes and functions
from .core import (
    ChunkMetadata,
    QualityScore,
    ChunkQualityScorer,
    DuplicateDetector,
    DataDriftDetector,
    filter_low_quality_chunks,
    remove_duplicates,
)

# Re-export config helpers
from .config import (
    get_quality_config,
    get_duplicate_config,
    get_drift_config,
    get_alert_thresholds,
    get_clients,
    validate_config,
    # Constants
    DEFAULT_MIN_QUALITY_SCORE,
    DEFAULT_OPTIMAL_LENGTH_MIN,
    DEFAULT_OPTIMAL_LENGTH_MAX,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_NUM_PERMUTATIONS,
    DEFAULT_SIGNIFICANCE_LEVEL,
    DEFAULT_DRIFT_THRESHOLD,
    ENABLE_PROMETHEUS,
)

__all__ = [
    # Core classes
    "ChunkMetadata",
    "QualityScore",
    "ChunkQualityScorer",
    "DuplicateDetector",
    "DataDriftDetector",
    # Core functions
    "filter_low_quality_chunks",
    "remove_duplicates",
    # Config helpers
    "get_quality_config",
    "get_duplicate_config",
    "get_drift_config",
    "get_alert_thresholds",
    "get_clients",
    "validate_config",
    # Config constants
    "DEFAULT_MIN_QUALITY_SCORE",
    "DEFAULT_OPTIMAL_LENGTH_MIN",
    "DEFAULT_OPTIMAL_LENGTH_MAX",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_NUM_PERMUTATIONS",
    "DEFAULT_SIGNIFICANCE_LEVEL",
    "DEFAULT_DRIFT_THRESHOLD",
    "ENABLE_PROMETHEUS",
]

__version__ = "1.0.0"
