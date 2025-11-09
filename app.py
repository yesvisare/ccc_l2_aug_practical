"""
FastAPI wrapper for M5.4: Vector Index Management

Provides REST API endpoints for:
- Health checks
- Backup operations
- Blue-green deployments
- Migration management
- Cost estimation

No business logic here - all functionality imported from m5_4_vector_index package.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from m5_4_vector_index.config import get_clients, Config, validate_config
from m5_4_vector_index.core import (
    IndexBackupManager,
    BlueGreenDeploymentManager,
    IndexMigrationManager,
    CostOptimizationCalculator
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M5.4: Vector Index Management",
    description="Production-grade vector index backup, blue-green deployment, and migration API",
    version="1.0.0"
)

# Initialize clients globally
clients = get_clients()
backup_mgr = None
bg_mgr = None
migration_mgr = None
cost_calc = CostOptimizationCalculator(
    cost_per_million_queries=Config.COST_PER_MILLION_QUERIES,
    cost_per_million_upserts=Config.COST_PER_MILLION_UPSERTS,
    cost_per_gb_storage_monthly=Config.COST_PER_GB_STORAGE_MONTHLY,
    cost_per_gb_transfer=Config.COST_PER_GB_TRANSFER
)

# Initialize managers if clients available
if clients['s3']:
    backup_mgr = IndexBackupManager(
        clients['pinecone'],
        clients['s3'],
        Config.S3_BACKUP_BUCKET
    )

if clients['redis']:
    bg_mgr = BlueGreenDeploymentManager(clients['pinecone'], clients['redis'])

if clients['pinecone']:
    migration_mgr = IndexMigrationManager(clients['pinecone'])


# ============================================
# Pydantic Models
# ============================================

class BackupRequest(BaseModel):
    index_name: str = Field(..., description="Pinecone index name")
    namespace: str = Field("", description="Namespace to backup")
    prefix: str = Field("backups", description="S3 key prefix")


class RestoreRequest(BaseModel):
    s3_key: str = Field(..., description="S3 key of backup file")
    target_index_name: str = Field(..., description="Target index name")
    target_namespace: str = Field("", description="Target namespace")
    verify_checksum: bool = Field(True, description="Verify MD5 checksum")


class BlueGreenCreateRequest(BaseModel):
    blue_index_name: str = Field(..., description="Current production index")
    green_index_name: str = Field(..., description="New index name")
    dimension: int = Field(1536, description="Vector dimension")
    metric: str = Field("cosine", description="Distance metric")
    pods: int = Field(1, description="Number of pods")
    replicas: int = Field(1, description="Number of replicas")


class BlueGreenSwitchRequest(BaseModel):
    blue_index_name: str = Field(..., description="Current production index")
    green_index_name: str = Field(..., description="New index to switch to")


class MigrationRequest(BaseModel):
    source_index_name: str = Field(..., description="Source index")
    target_index_name: str = Field(..., description="Target index")
    source_namespace: str = Field("", description="Source namespace")
    target_namespace: str = Field("", description="Target namespace")
    verify_sample_size: int = Field(100, description="Verification sample size")


class CostEstimateRequest(BaseModel):
    vector_count: int = Field(..., description="Number of vectors")
    dimension: int = Field(1536, description="Vector dimension")
    days_dual_index: int = Field(7, description="Days running both indexes")


# ============================================
# Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns status of all clients and managers.
    """
    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "clients": {
            "pinecone": clients['pinecone'] is not None,
            "s3": clients['s3'] is not None,
            "redis": clients['redis'] is not None
        },
        "managers": {
            "backup": backup_mgr is not None,
            "blue_green": bg_mgr is not None,
            "migration": migration_mgr is not None,
            "cost_calc": cost_calc is not None
        }
    })


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "M5.4: Vector Index Management API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "backup": "/backup",
            "restore": "/restore",
            "list_backups": "/backups",
            "blue_green_create": "/blue-green/create",
            "blue_green_switch": "/blue-green/switch",
            "blue_green_rollback": "/blue-green/rollback",
            "migrate": "/migrate",
            "cost_estimate": "/cost/estimate"
        }
    }


@app.post("/backup")
async def create_backup(request: BackupRequest, background_tasks: BackgroundTasks):
    """
    Create a backup of a Pinecone index to S3.
    Returns backup metadata or skip message if S3 unavailable.
    """
    if not backup_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "S3 client not configured (missing AWS credentials)"
            }
        )

    try:
        logger.info(f"Starting backup for {request.index_name}/{request.namespace}")

        metadata = backup_mgr.backup_index(
            request.index_name,
            request.namespace,
            request.prefix
        )

        if metadata:
            return {
                "success": True,
                "backup_id": metadata.backup_id,
                "timestamp": metadata.timestamp,
                "vector_count": metadata.vector_count,
                "compressed_size_bytes": metadata.compressed_size_bytes,
                "s3_key": metadata.s3_key,
                "checksum": metadata.checksum
            }
        else:
            raise HTTPException(status_code=500, detail="Backup failed")

    except Exception as e:
        logger.error(f"Backup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/restore")
async def restore_backup(request: RestoreRequest):
    """
    Restore vectors from S3 backup to a Pinecone index.
    Returns success status or skip message if S3 unavailable.
    """
    if not backup_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "S3 client not configured (missing AWS credentials)"
            }
        )

    try:
        logger.info(f"Restoring from {request.s3_key} to {request.target_index_name}")

        success = backup_mgr.restore_index(
            request.s3_key,
            request.target_index_name,
            request.target_namespace,
            request.verify_checksum
        )

        return {
            "success": success,
            "s3_key": request.s3_key,
            "target_index": request.target_index_name,
            "checksum_verified": request.verify_checksum
        }

    except Exception as e:
        logger.error(f"Restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backups")
async def list_backups(index_name: Optional[str] = None, prefix: str = "backups"):
    """
    List all backups in S3, optionally filtered by index name.
    """
    if not backup_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "S3 client not configured (missing AWS credentials)",
                "backups": []
            }
        )

    try:
        backups = backup_mgr.list_backups(index_name, prefix)
        return {
            "count": len(backups),
            "backups": backups
        }

    except Exception as e:
        logger.error(f"List backups error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/blue-green/create")
async def create_green_index(request: BlueGreenCreateRequest):
    """
    Create a new "green" index for blue-green deployment.
    """
    if not bg_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "Redis or Pinecone client not configured"
            }
        )

    try:
        success = bg_mgr.create_green_index(
            request.blue_index_name,
            request.green_index_name,
            request.dimension,
            request.metric,
            request.pods,
            request.replicas
        )

        return {
            "success": success,
            "blue_index": request.blue_index_name,
            "green_index": request.green_index_name
        }

    except Exception as e:
        logger.error(f"Create green index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/blue-green/switch")
async def switch_traffic(request: BlueGreenSwitchRequest):
    """
    Switch traffic from blue to green index atomically.
    """
    if not bg_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "Redis client not configured"
            }
        )

    try:
        success = bg_mgr.switch_traffic(
            request.blue_index_name,
            request.green_index_name
        )

        return {
            "success": success,
            "from": request.blue_index_name,
            "to": request.green_index_name,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Switch traffic error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/blue-green/rollback")
async def rollback_to_blue(blue_index_name: str):
    """
    Rollback to blue index instantly.
    """
    if not bg_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "Redis client not configured"
            }
        )

    try:
        success = bg_mgr.rollback(blue_index_name)

        return {
            "success": success,
            "rolled_back_to": blue_index_name,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Rollback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/migrate")
async def migrate_index(request: MigrationRequest):
    """
    Migrate vectors from source to target index with verification.
    """
    if not migration_mgr:
        return JSONResponse(
            status_code=200,
            content={
                "skipped": True,
                "reason": "Pinecone client not configured"
            }
        )

    try:
        result = migration_mgr.migrate_index(
            request.source_index_name,
            request.target_index_name,
            request.source_namespace,
            request.target_namespace,
            transform_fn=None,  # No transformation in API (can be extended)
            verify_sample_size=request.verify_sample_size
        )

        return {
            "success": result.success,
            "vectors_migrated": result.vectors_migrated,
            "vectors_verified": result.vectors_verified,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors
        }

    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cost/estimate")
async def estimate_cost(request: CostEstimateRequest):
    """
    Estimate cost for a blue-green migration.
    """
    try:
        breakdown = cost_calc.estimate_migration_cost(
            request.vector_count,
            request.dimension,
            request.days_dual_index
        )

        return {
            "vector_count": request.vector_count,
            "dimension": request.dimension,
            "days_dual_index": request.days_dual_index,
            "cost_breakdown": {
                "storage": breakdown.storage_cost,
                "queries": breakdown.query_cost,
                "upserts": breakdown.upsert_cost,
                "transfer": breakdown.transfer_cost,
                "total": breakdown.total_cost
            }
        }

    except Exception as e:
        logger.error(f"Cost estimate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """
    Prometheus-compatible metrics endpoint (optional).
    """
    # Basic metrics - extend with prometheus_client if needed
    return {
        "uptime": "active",
        "clients_active": sum(1 for c in clients.values() if c is not None),
        "managers_initialized": sum(1 for m in [backup_mgr, bg_mgr, migration_mgr] if m is not None)
    }


# ============================================
# Startup and Shutdown
# ============================================

@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("=== M5.4 Vector Index Management API Starting ===")
    logger.info(f"Pinecone: {'✓' if clients['pinecone'] else '✗'}")
    logger.info(f"S3: {'✓' if clients['s3'] else '✗'}")
    logger.info(f"Redis: {'✓' if clients['redis'] else '✗'}")

    if not validate_config():
        logger.warning("Configuration incomplete - some features unavailable")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("=== M5.4 Vector Index Management API Shutting Down ===")


# ============================================
# Uvicorn Runner
# ============================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting development server...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
