"""
Configuration management for Module 8.4: Human-in-the-Loop Evaluation

Reads environment variables from .env file and provides typed configuration.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration for HITL evaluation system."""

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "feedback.db")

    # Active Learning
    UNCERTAINTY_WEIGHT: float = float(os.getenv("UNCERTAINTY_WEIGHT", "0.5"))
    NEGATIVE_FEEDBACK_BOOST: float = float(os.getenv("NEGATIVE_FEEDBACK_BOOST", "0.5"))
    N_SELECT_DAILY: int = int(os.getenv("N_SELECT_DAILY", "50"))
    N_DIVERSITY_CLUSTERS: int = int(os.getenv("N_DIVERSITY_CLUSTERS", "10"))

    # Inter-Annotator Agreement
    MIN_IAA_THRESHOLD: float = float(os.getenv("MIN_IAA_THRESHOLD", "0.70"))

    # Feedback Loop
    MIN_CONFIDENCE_FOR_TRAINING: float = float(os.getenv("MIN_CONFIDENCE_FOR_TRAINING", "0.7"))
    FEEDBACK_RESPONSE_RATE_TARGET: float = float(os.getenv("FEEDBACK_RESPONSE_RATE_TARGET", "0.05"))

    # Label Studio (optional)
    LABEL_STUDIO_URL: Optional[str] = os.getenv("LABEL_STUDIO_URL")
    LABEL_STUDIO_API_KEY: Optional[str] = os.getenv("LABEL_STUDIO_API_KEY")
    LABEL_STUDIO_PROJECT_ID: Optional[str] = os.getenv("LABEL_STUDIO_PROJECT_ID")

    # API Configuration
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")

    # Monitoring
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "false").lower() == "true"

    @classmethod
    def is_label_studio_configured(cls) -> bool:
        """Check if Label Studio is properly configured."""
        return all([
            cls.LABEL_STUDIO_URL,
            cls.LABEL_STUDIO_API_KEY,
            cls.LABEL_STUDIO_PROJECT_ID
        ])


def get_config() -> Config:
    """Get configuration instance."""
    return Config()


# Optional: Label Studio client setup
def get_label_studio_client():
    """
    Get Label Studio SDK client if configured.
    Returns None if Label Studio is not configured.
    """
    if not Config.is_label_studio_configured():
        return None

    try:
        from label_studio_sdk import Client
        client = Client(
            url=Config.LABEL_STUDIO_URL,
            api_key=Config.LABEL_STUDIO_API_KEY
        )
        return client
    except ImportError:
        print("⚠️ label-studio-sdk not installed. Install with: pip install label-studio-sdk")
        return None
    except Exception as e:
        print(f"⚠️ Failed to initialize Label Studio client: {e}")
        return None


if __name__ == "__main__":
    config = get_config()
    print("=== Configuration ===")
    print(f"DB Path: {config.DB_PATH}")
    print(f"Uncertainty Weight: {config.UNCERTAINTY_WEIGHT}")
    print(f"N Select Daily: {config.N_SELECT_DAILY}")
    print(f"Min IAA Threshold: {config.MIN_IAA_THRESHOLD}")
    print(f"Label Studio Configured: {config.is_label_studio_configured()}")
    print(f"API Port: {config.API_PORT}")
