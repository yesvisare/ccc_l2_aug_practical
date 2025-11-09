"""
M6.3: RBAC & Multi-Level Access Control

Enterprise role-based access control for RAG systems.
"""

from .core import (
    RBACManager,
    User,
    Role,
    PermissionLog,
    AccessLevel,
    RoleName,
    query_with_rbac
)

from .config import (
    Config,
    get_rbac_manager,
    get_pinecone_client,
    get_redis_client,
    has_pinecone,
    has_redis
)

__all__ = [
    # Core RBAC
    'RBACManager',
    'User',
    'Role',
    'PermissionLog',
    'AccessLevel',
    'RoleName',
    'query_with_rbac',

    # Configuration
    'Config',
    'get_rbac_manager',
    'get_pinecone_client',
    'get_redis_client',
    'has_pinecone',
    'has_redis',
]

__version__ = '1.0.0'
