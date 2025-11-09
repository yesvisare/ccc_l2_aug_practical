"""
Module 8.3: Regression Testing & CI/CD for RAG Systems

This package implements automated quality assurance for RAG systems including:
- Regression test suite
- DVC model versioning
- Safe deployment with canary testing
- Threshold calibration
- Cost estimation
"""

__version__ = "1.0.0"

# Export main components for easier imports
from .regression import (
    RegressionMetrics,
    RegressionTestSuite,
    FlakyTestHandler,
    ThresholdCalibrator,
    DVCVersionManager,
    SafeDeployment,
    DVCConflictResolver,
    estimate_cicd_costs,
    should_use_cicd,
)

__all__ = [
    "RegressionMetrics",
    "RegressionTestSuite",
    "FlakyTestHandler",
    "ThresholdCalibrator",
    "DVCVersionManager",
    "SafeDeployment",
    "DVCConflictResolver",
    "estimate_cicd_costs",
    "should_use_cicd",
]
