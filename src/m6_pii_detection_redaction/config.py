"""
Configuration module for PII Detection & Redaction.
Loads environment variables and provides configuration constants.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for PII detection and redaction."""

    # PII Detection Settings
    PII_CONFIDENCE_THRESHOLD: float = float(os.getenv("PII_CONFIDENCE_THRESHOLD", "0.5"))
    PII_REDACTION_STRATEGY: str = os.getenv("PII_REDACTION_STRATEGY", "replacement")

    # Processing Settings
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "4"))
    ENABLE_PARALLEL_PROCESSING: bool = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() == "true"

    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_LOG_MASKING: bool = os.getenv("ENABLE_LOG_MASKING", "true").lower() == "true"

    # Optional: AWS Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # Optional: GCP Configuration
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    GCP_PROJECT_ID: Optional[str] = os.getenv("GCP_PROJECT_ID")

    # Optional: Metrics
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "false").lower() == "true"
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))

    # Supported PII Entity Types
    DEFAULT_ENTITY_TYPES = [
        "CREDIT_CARD",
        "CRYPTO",
        "DATE_TIME",
        "EMAIL_ADDRESS",
        "IBAN_CODE",
        "IP_ADDRESS",
        "NRP",
        "LOCATION",
        "PERSON",
        "PHONE_NUMBER",
        "MEDICAL_LICENSE",
        "URL",
        "US_BANK_NUMBER",
        "US_DRIVER_LICENSE",
        "US_ITIN",
        "US_PASSPORT",
        "US_SSN",
    ]

    # Redaction Strategy Constants
    REDACTION_STRATEGIES = {
        "masking": "mask",
        "replacement": "replace",
        "hashing": "hash"
    }


def get_clients():
    """
    Initialize and return external service clients if credentials are available.
    Returns None if credentials are not configured.
    """
    clients = {}

    # AWS Client (for Macie/Comprehend)
    if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
        try:
            import boto3
            clients['aws'] = boto3.Session(
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
        except ImportError:
            pass

    # GCP Client (for DLP API)
    if Config.GOOGLE_APPLICATION_CREDENTIALS and Config.GCP_PROJECT_ID:
        try:
            from google.cloud import dlp_v2
            clients['gcp_dlp'] = dlp_v2.DlpServiceClient()
        except ImportError:
            pass

    return clients if clients else None


def load_config() -> Config:
    """
    Load and return the configuration instance.

    Returns:
        Config instance with loaded environment variables
    """
    return config


# Export configuration instance
config = Config()
