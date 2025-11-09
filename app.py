"""
FastAPI application for Secrets Management & Rotation module.

This is the entrypoint for the web service. All business logic lives in
m6_secrets package - this file only handles HTTP routing.

Endpoints:
- GET /health - Health check with Vault connectivity status
- POST /query - RAG query endpoint (from Level 1 M3)
- POST /admin/rotate-key - Trigger manual secret rotation
- GET /metrics - Prometheus metrics (if enabled)
"""

from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import os
from typing import Optional

from m6_secrets.core import (
    VaultClient,
    ResilientVaultClient,
    SecretRotationManager
)
from m6_secrets.config import AppConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state (initialized on startup)
app_config: Optional[AppConfig] = None
vault_client: Optional[VaultClient] = None
rotation_manager: Optional[SecretRotationManager] = None
openai_client = None
pinecone_index = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Fetches secrets from Vault on startup.
    """
    global app_config, vault_client, rotation_manager, openai_client, pinecone_index

    try:
        # Load configuration
        app_config = AppConfig()
        logger.info(f"Starting in {app_config.environment} environment")

        # Initialize Vault client with resilience
        if app_config.vault.is_configured():
            vault_client = ResilientVaultClient(
                vault_addr=app_config.vault.addr,
                vault_token=app_config.vault.token,
                environment=app_config.environment,
                max_retries=3,
                fallback_env=app_config.fallback_to_env
            )

            # Initialize rotation manager
            rotation_manager = SecretRotationManager(vault_client)

            # Fetch secrets
            try:
                secrets = vault_client.get_rag_secrets()
                logger.info(f"Fetched {len(secrets)} secrets from Vault")

                # Initialize OpenAI client if key available
                if secrets.get('openai_key'):
                    from openai import OpenAI
                    openai_client = OpenAI(api_key=secrets['openai_key'])
                    logger.info("✅ OpenAI client initialized")

                # Initialize Pinecone if key available
                if secrets.get('pinecone_key'):
                    try:
                        from pinecone import Pinecone
                        pc = Pinecone(api_key=secrets['pinecone_key'])
                        # pinecone_index = pc.Index("rag-system")
                        logger.info("✅ Pinecone client initialized")
                    except Exception as e:
                        logger.warning(f"⚠️  Pinecone initialization failed: {e}")

            except Exception as e:
                logger.warning(f"⚠️  Failed to fetch secrets: {e}")
                if not app_config.fallback_to_env:
                    raise

        else:
            logger.warning("⚠️  Vault not configured - running without secret management")

        logger.info("🚀 Application startup complete")

        yield  # Application runs here

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    finally:
        logger.info("Application shutdown")


# Create FastAPI app
app = FastAPI(
    title="Secrets Management & Rotation",
    description="Module 6.2: Enterprise-grade secrets management with HashiCorp Vault",
    version="1.0.0",
    lifespan=lifespan
)


# Request/Response models
class HealthResponse(BaseModel):
    status: str
    vault_connected: bool
    secrets_available: bool
    environment: str


class QueryRequest(BaseModel):
    query: str
    max_results: int = 5


class QueryResponse(BaseModel):
    query: str
    response: str
    sources: list = []


class RotationRequest(BaseModel):
    secret_key: str = "openai_key"
    new_value: str


class RotationResponse(BaseModel):
    status: str
    message: str
    downtime_seconds: int


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Verifies Vault connection and secret availability.
    """
    try:
        vault_connected = vault_client is not None
        secrets_available = False

        if vault_client:
            try:
                secrets = vault_client.get_rag_secrets()
                secrets_available = len(secrets) > 0
            except Exception as e:
                logger.warning(f"Health check: Vault read failed - {e}")

        return HealthResponse(
            status="healthy" if vault_connected else "degraded",
            vault_connected=vault_connected,
            secrets_available=secrets_available,
            environment=app_config.environment if app_config else "unknown"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    RAG query endpoint using Vault-managed secrets.

    This is a placeholder for your Level 1 M3 RAG implementation.
    The important part is that it uses clients initialized from Vault secrets.
    """
    if not openai_client:
        return QueryResponse(
            query=request.query,
            response="⚠️ Skipping API calls (no OpenAI client initialized)",
            sources=[]
        )

    try:
        # Placeholder RAG logic
        # In real implementation, this would:
        # 1. Generate embedding with OpenAI
        # 2. Search Pinecone for similar vectors
        # 3. Generate response with context

        with rotation_manager.track_request() if rotation_manager else nullcontext():
            # Simple echo response for demonstration
            response_text = f"[Demo] Query received: '{request.query}'. In production, this would return RAG results using Vault-managed OpenAI/Pinecone credentials."

            return QueryResponse(
                query=request.query,
                response=response_text,
                sources=["demo-source-1", "demo-source-2"]
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@app.post("/admin/rotate-key", response_model=RotationResponse)
async def rotate_key(request: RotationRequest):
    """
    Admin endpoint to manually trigger key rotation.

    WARNING: In production, this should be protected with authentication/authorization.
    """
    if not vault_client or not rotation_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vault or rotation manager not initialized"
        )

    try:
        # Rotate secret in Vault
        success = vault_client.rotate_secret(
            path=f"rag-system/{app_config.environment}",
            key=request.secret_key,
            new_value=request.new_value
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Secret rotation failed in Vault"
            )

        # If rotating OpenAI key, update client
        if request.secret_key == "openai_key":
            global openai_client
            from openai import OpenAI

            openai_client = rotation_manager.rotate_openai_key(
                new_key=request.new_value,
                client_factory=OpenAI,
                old_client=openai_client
            )

        return RotationResponse(
            status="success",
            message=f"Secret '{request.secret_key}' rotated successfully",
            downtime_seconds=0
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rotation failed: {str(e)}"
        )


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint (optional).

    In production, this would expose:
    - secret_fetch_duration_seconds (histogram)
    - secret_cache_hit_rate (gauge)
    - rotation_count_total (counter)
    - vault_connection_errors_total (counter)
    """
    if not app_config or not app_config.enable_metrics:
        return {
            "skipped": True,
            "reason": "Metrics not enabled. Set ENABLE_METRICS=true"
        }

    # Placeholder metrics
    return {
        "vault_connected": vault_client is not None,
        "secrets_cached": 0,  # Would come from cache stats
        "rotations_total": 0,  # Would come from rotation manager
        "active_requests": rotation_manager.active_requests if rotation_manager else 0
    }


# Helper context manager
from contextlib import nullcontext


if __name__ == "__main__":
    """
    Run the application locally for development.

    Usage:
        python app.py

    Or with uvicorn directly:
        uvicorn app:app --reload --port 8000
    """
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
