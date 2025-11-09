"""
Configuration management for RAGAS Evaluation Framework.
Reads from environment variables and provides validated settings.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration settings for RAGAS evaluation system."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # Directory Configuration
    GOLDEN_SET_DIR: Path = Path(os.getenv("GOLDEN_SET_DIR", "./golden_sets"))
    RESULTS_DIR: Path = Path(os.getenv("RESULTS_DIR", "./evaluation_results"))
    CHECKPOINT_DIR: Path = Path(os.getenv("CHECKPOINT_DIR", "./checkpoints"))

    # Domain-Specific Thresholds
    DOMAIN: str = os.getenv("DOMAIN", "general")
    FAITHFULNESS_THRESHOLD: float = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.70"))
    ANSWER_RELEVANCY_THRESHOLD: float = float(os.getenv("ANSWER_RELEVANCY_THRESHOLD", "0.70"))
    CONTEXT_PRECISION_THRESHOLD: float = float(os.getenv("CONTEXT_PRECISION_THRESHOLD", "0.70"))
    CONTEXT_RECALL_THRESHOLD: float = float(os.getenv("CONTEXT_RECALL_THRESHOLD", "0.70"))

    # Pipeline Configuration
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "20"))
    EVALUATION_TIMEOUT: int = int(os.getenv("EVALUATION_TIMEOUT", "600"))
    RATE_LIMIT_DELAY: int = int(os.getenv("RATE_LIMIT_DELAY", "2"))

    # Cost Configuration
    MAX_MONTHLY_COST_USD: float = float(os.getenv("MAX_MONTHLY_COST_USD", "200"))
    ALERT_THRESHOLD_COST_USD: float = float(os.getenv("ALERT_THRESHOLD_COST_USD", "150"))

    # MLflow Configuration (optional)
    MLFLOW_TRACKING_URI: Optional[str] = os.getenv("MLFLOW_TRACKING_URI")
    MLFLOW_EXPERIMENT_NAME: str = os.getenv("MLFLOW_EXPERIMENT_NAME", "ragas_evaluation")

    @classmethod
    def validate(cls) -> bool:
        """
        Validate configuration settings.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        issues = []

        if not cls.OPENAI_API_KEY:
            issues.append("OPENAI_API_KEY not set")
            logger.warning("⚠️  OPENAI_API_KEY not configured - evaluation will skip API calls")

        # Create directories if they don't exist
        for dir_path in [cls.GOLDEN_SET_DIR, cls.RESULTS_DIR, cls.CHECKPOINT_DIR]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {dir_path}: {e}")

        if issues:
            logger.error("Configuration issues found:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False

        logger.info("✅ Configuration validated successfully")
        return True

    @classmethod
    def get_domain_thresholds(cls) -> Dict[str, float]:
        """
        Get domain-specific thresholds as a dictionary.

        Returns:
            Dict[str, float]: Threshold values for each metric
        """
        return {
            "faithfulness": cls.FAITHFULNESS_THRESHOLD,
            "answer_relevancy": cls.ANSWER_RELEVANCY_THRESHOLD,
            "context_precision": cls.CONTEXT_PRECISION_THRESHOLD,
            "context_recall": cls.CONTEXT_RECALL_THRESHOLD
        }

    @classmethod
    def get_openai_client(cls):
        """
        Get configured OpenAI client.

        Returns:
            OpenAI client instance or None if not configured
        """
        if not cls.OPENAI_API_KEY:
            logger.warning("⚠️  OpenAI API key not configured")
            return None

        try:
            from openai import OpenAI
            return OpenAI(api_key=cls.OPENAI_API_KEY)
        except ImportError:
            logger.error("❌ openai package not installed")
            return None

    @classmethod
    def has_openai_key(cls) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(cls.OPENAI_API_KEY and cls.OPENAI_API_KEY.startswith("sk-"))


# Validate configuration on module load
if __name__ != "__main__":
    Config.validate()
