"""
FastAPI entrypoint for M6.3 RBAC module.

Provides REST API endpoints for:
- Health checks
- User management
- Permission queries
- Document access with RBAC filtering
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import time

from config import Config, get_rbac_manager, has_pinecone

# Import from module with hyphens needs special handling
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("l2_m6_rbac", "/home/user/ccc_l2_aug_practical/l2_m6_rbac_multi-level_access.py")
rbac_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rbac_module)
User = rbac_module.User
RoleName = rbac_module.RoleName
AccessLevel = rbac_module.AccessLevel

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M6.3: RBAC & Multi-Level Access Control",
    description="Role-based access control for enterprise RAG systems",
    version="1.0.0"
)

# Optional Prometheus metrics
if Config.ENABLE_METRICS:
    try:
        from prometheus_client import Counter, Histogram, generate_latest
        from starlette.responses import Response

        REQUEST_COUNT = Counter('rbac_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
        REQUEST_LATENCY = Histogram('rbac_request_latency_seconds', 'Request latency', ['endpoint'])
        PERMISSION_CHECKS = Counter('rbac_permission_checks_total', 'Permission checks', ['result'])

        @app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint"""
            return Response(generate_latest(), media_type="text/plain")

        logger.info("Prometheus metrics enabled at /metrics")
    except ImportError:
        logger.warning("prometheus-client not installed, metrics disabled")
        Config.ENABLE_METRICS = False


# Request/Response Models

class UserCreate(BaseModel):
    """Create user request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    api_key: str = Field(..., min_length=10)
    roles: List[str] = Field(default=["viewer"])


class UserResponse(BaseModel):
    """User response"""
    id: int
    username: str
    email: Optional[str]
    roles: List[str]
    active: bool


class RoleAssignment(BaseModel):
    """Role assignment request"""
    username: str
    role_name: str


class PermissionCheck(BaseModel):
    """Permission check request"""
    resource: str
    action: str


class QueryRequest(BaseModel):
    """Document query request"""
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)


class QueryResponse(BaseModel):
    """Query response"""
    query: str
    results: List[Dict[str, Any]]
    accessible_levels: List[str]
    skipped: bool = False
    reason: Optional[str] = None


# Dependencies

async def get_current_user(
    x_api_key: Optional[str] = Header(None),
    request: Request = None
) -> User:
    """
    Extract and validate user from API key header.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        User object

    Raises:
        HTTPException: If API key invalid or missing
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    try:
        rbac = get_rbac_manager()
        user = rbac.get_user_by_api_key(x_api_key)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")

        if not user.active:
            raise HTTPException(status_code=403, detail="User account disabled")

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


def require_permission(resource: str, action: str):
    """
    Factory dependency for permission checking.

    Args:
        resource: Resource identifier
        action: Action to perform

    Returns:
        Dependency function
    """
    async def check_permission(user: User = Depends(get_current_user)):
        rbac = get_rbac_manager()

        if not rbac.check_permission(user, resource, action):
            if Config.ENABLE_METRICS:
                PERMISSION_CHECKS.labels(result='denied').inc()

            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {action} on {resource}"
            )

        if Config.ENABLE_METRICS:
            PERMISSION_CHECKS.labels(result='allowed').inc()

        return user

    return check_permission


# Middleware

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Request logging and metrics middleware"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time

    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )

    if Config.ENABLE_METRICS:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

    return response


# Health & Status Endpoints

@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status with component checks
    """
    try:
        rbac = get_rbac_manager()

        # Check database connection
        db = rbac.get_session()
        db.execute("SELECT 1")
        db.close()
        db_status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "components": {
            "database": db_status,
            "pinecone": "configured" if has_pinecone() else "not_configured"
        }
    }


@app.get("/stats")
async def get_stats(user: User = Depends(get_current_user)):
    """
    Get permission statistics (requires authentication).

    Returns:
        Permission check statistics
    """
    try:
        rbac = get_rbac_manager()
        stats = rbac.get_permission_stats(hours=24)
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


# User Management Endpoints

@app.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_permission("user", "manage"))
):
    """
    Create new user (admin only).

    Args:
        user_data: User creation data

    Returns:
        Created user
    """
    try:
        rbac = get_rbac_manager()

        # Validate roles
        for role_name in user_data.roles:
            if role_name not in [r.value for r in RoleName]:
                raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")

        user = rbac.create_user(
            username=user_data.username,
            api_key=user_data.api_key,
            email=user_data.email,
            roles=user_data.roles
        )

        if not user:
            raise HTTPException(status_code=400, detail="Failed to create user")

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            roles=user.get_role_names(),
            active=user.active
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(status_code=500, detail="User creation failed")


@app.post("/users/roles/assign")
async def assign_role(
    assignment: RoleAssignment,
    current_user: User = Depends(require_permission("role", "manage"))
):
    """
    Assign role to user (admin only).

    Args:
        assignment: Role assignment data

    Returns:
        Success message
    """
    try:
        rbac = get_rbac_manager()

        if assignment.role_name not in [r.value for r in RoleName]:
            raise HTTPException(status_code=400, detail=f"Invalid role: {assignment.role_name}")

        success = rbac.assign_role(assignment.username, assignment.role_name)

        if not success:
            raise HTTPException(status_code=404, detail="User or role not found")

        return {"message": f"Role {assignment.role_name} assigned to {assignment.username}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Role assignment failed: {e}")
        raise HTTPException(status_code=500, detail="Role assignment failed")


@app.post("/users/roles/revoke")
async def revoke_role(
    assignment: RoleAssignment,
    current_user: User = Depends(require_permission("role", "manage"))
):
    """
    Revoke role from user (admin only).

    Args:
        assignment: Role revocation data

    Returns:
        Success message
    """
    try:
        rbac = get_rbac_manager()

        success = rbac.revoke_role(assignment.username, assignment.role_name)

        if not success:
            raise HTTPException(status_code=404, detail="User or role not found")

        return {"message": f"Role {assignment.role_name} revoked from {assignment.username}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Role revocation failed: {e}")
        raise HTTPException(status_code=500, detail="Role revocation failed")


# Permission Check Endpoints

@app.post("/permissions/check")
async def check_permission_endpoint(
    check: PermissionCheck,
    user: User = Depends(get_current_user)
):
    """
    Check if current user has permission.

    Args:
        check: Permission check data

    Returns:
        Permission check result
    """
    try:
        rbac = get_rbac_manager()
        allowed = rbac.check_permission(user, check.resource, check.action)

        return {
            "allowed": allowed,
            "user": user.username,
            "resource": check.resource,
            "action": check.action
        }

    except Exception as e:
        logger.error(f"Permission check failed: {e}")
        raise HTTPException(status_code=500, detail="Permission check failed")


@app.get("/permissions/accessible-levels")
async def get_accessible_levels(user: User = Depends(get_current_user)):
    """
    Get document access levels for current user.

    Returns:
        List of accessible access levels
    """
    try:
        rbac = get_rbac_manager()
        levels = rbac.get_accessible_levels(user)

        return {
            "user": user.username,
            "roles": user.get_role_names(),
            "accessible_levels": levels
        }

    except Exception as e:
        logger.error(f"Failed to get accessible levels: {e}")
        raise HTTPException(status_code=500, detail="Failed to get accessible levels")


# Document Query Endpoints

@app.post("/query", response_model=QueryResponse)
async def query_documents(
    query_req: QueryRequest,
    user: User = Depends(get_current_user)
):
    """
    Query documents with RBAC filtering.

    Args:
        query_req: Query parameters

    Returns:
        Filtered query results
    """
    try:
        rbac = get_rbac_manager()

        # Check if Pinecone configured
        if not has_pinecone():
            return QueryResponse(
                query=query_req.query,
                results=[],
                accessible_levels=rbac.get_accessible_levels(user),
                skipped=True,
                reason="Pinecone not configured"
            )

        # Get RBAC filter
        pinecone_filter = rbac.get_pinecone_filter(user)
        accessible_levels = rbac.get_accessible_levels(user)

        logger.info(f"Query by {user.username} with filter: {pinecone_filter}")

        # TODO: Implement actual Pinecone query with embedding
        # For now, return mock response
        results = []

        return QueryResponse(
            query=query_req.query,
            results=results,
            accessible_levels=accessible_levels,
            skipped=True,
            reason="Pinecone query not implemented (demo mode)"
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail="Query failed")


# Error Handlers

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


# Startup/Shutdown Events

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting RBAC API server...")
    logger.info(f"Database: {Config.DATABASE_URL}")
    logger.info(f"Pinecone: {'Configured' if has_pinecone() else 'Not configured'}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RBAC API server...")


# Local development runner
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True,
        log_level=Config.LOG_LEVEL.lower()
    )
