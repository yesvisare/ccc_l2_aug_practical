"""
Smoke tests for M6.3 RBAC module.

Tests basic functionality without requiring external services.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import from package
from m6_rbac import core as rbac_module
from m6_rbac import Config


def test_config_loads():
    """Test that configuration loads without errors"""
    try:
        assert Config.DATABASE_URL is not None
        print("✓ Config loads successfully")
    except Exception as e:
        pytest.fail(f"Config failed to load: {e}")


def test_access_level_enum():
    """Test AccessLevel enum values"""
    assert rbac_module.AccessLevel.PUBLIC.value == "public"
    assert rbac_module.AccessLevel.INTERNAL.value == "internal"
    assert rbac_module.AccessLevel.CONFIDENTIAL.value == "confidential"
    print("✓ AccessLevel enum correct")


def test_role_name_enum():
    """Test RoleName enum values"""
    assert rbac_module.RoleName.ADMIN.value == "admin"
    assert rbac_module.RoleName.EDITOR.value == "editor"
    assert rbac_module.RoleName.VIEWER.value == "viewer"
    print("✓ RoleName enum correct")


def test_rbac_manager_init_with_sqlite():
    """Test RBAC manager initialization with SQLite (no external deps)"""
    try:
        # Use in-memory SQLite for testing
        rbac = rbac_module.RBACManager("sqlite:///:memory:")
        assert rbac is not None
        assert rbac.enforcer is not None
        print("✓ RBAC Manager initializes with SQLite")
    except Exception as e:
        pytest.fail(f"RBAC Manager initialization failed: {e}")


def test_user_creation():
    """Test user creation flow"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    user = rbac.create_user(
        username="test_user",
        api_key="test_key_123",
        email="test@example.com",
        roles=["viewer"]
    )

    assert user is not None
    assert user.username == "test_user"
    assert user.email == "test@example.com"
    assert len(user.roles) == 1
    print("✓ User creation works")


def test_api_key_hashing():
    """Test API key hashing"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    api_key = "my_secret_key"
    hash1 = rbac.hash_api_key(api_key)
    hash2 = rbac.hash_api_key(api_key)

    # Same key should produce same hash
    assert hash1 == hash2

    # Different key should produce different hash
    hash3 = rbac.hash_api_key("different_key")
    assert hash1 != hash3

    print("✓ API key hashing consistent")


def test_user_lookup_by_api_key():
    """Test user retrieval by API key"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    api_key = "lookup_test_key"
    created_user = rbac.create_user(
        username="lookup_user",
        api_key=api_key,
        roles=["viewer"]
    )

    retrieved_user = rbac.get_user_by_api_key(api_key)

    assert retrieved_user is not None
    assert retrieved_user.username == created_user.username
    assert retrieved_user.id == created_user.id
    print("✓ User lookup by API key works")


def test_role_assignment():
    """Test role assignment to user"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    user = rbac.create_user(
        username="role_test_user",
        api_key="role_test_key",
        roles=["viewer"]
    )

    # Assign editor role
    success = rbac.assign_role("role_test_user", "editor")
    assert success is True

    # Verify user has both roles
    updated_user = rbac.get_user_by_api_key("role_test_key")
    role_names = updated_user.get_role_names()
    assert "viewer" in role_names
    assert "editor" in role_names
    print("✓ Role assignment works")


def test_role_revocation():
    """Test role revocation from user"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    user = rbac.create_user(
        username="revoke_test_user",
        api_key="revoke_test_key",
        roles=["viewer", "editor"]
    )

    # Revoke editor role
    success = rbac.revoke_role("revoke_test_user", "editor")
    assert success is True

    # Verify user only has viewer role
    updated_user = rbac.get_user_by_api_key("revoke_test_key")
    role_names = updated_user.get_role_names()
    assert "viewer" in role_names
    assert "editor" not in role_names
    print("✓ Role revocation works")


def test_permission_checking():
    """Test permission checking logic"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    # Create users with different roles
    admin = rbac.create_user("admin_user", "admin_key", roles=["admin"])
    editor = rbac.create_user("editor_user", "editor_key", roles=["editor"])
    viewer = rbac.create_user("viewer_user", "viewer_key", roles=["viewer"])

    # Viewer can read
    assert rbac.check_permission(viewer, "document", "read", log_check=False) is True

    # Viewer cannot write
    assert rbac.check_permission(viewer, "document", "write", log_check=False) is False

    # Editor can write
    assert rbac.check_permission(editor, "document", "write", log_check=False) is True

    # Admin can delete
    assert rbac.check_permission(admin, "document", "delete", log_check=False) is True

    # Editor cannot delete
    assert rbac.check_permission(editor, "document", "delete", log_check=False) is False

    print("✓ Permission checking works")


def test_accessible_levels():
    """Test document access level determination"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    admin = rbac.create_user("admin", "admin_key", roles=["admin"])
    editor = rbac.create_user("editor", "editor_key", roles=["editor"])
    viewer = rbac.create_user("viewer", "viewer_key", roles=["viewer"])

    # Admin has all levels
    admin_levels = rbac.get_accessible_levels(admin)
    assert set(admin_levels) == {"public", "internal", "confidential"}

    # Editor has public and internal
    editor_levels = rbac.get_accessible_levels(editor)
    assert set(editor_levels) == {"public", "internal"}

    # Viewer has only public
    viewer_levels = rbac.get_accessible_levels(viewer)
    assert set(viewer_levels) == {"public"}

    print("✓ Accessible levels correct")


def test_pinecone_filter_generation():
    """Test Pinecone metadata filter generation"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    admin = rbac.create_user("admin", "admin_key", roles=["admin"])
    editor = rbac.create_user("editor", "editor_key", roles=["editor"])
    viewer = rbac.create_user("viewer", "viewer_key", roles=["viewer"])

    # Check filter structure
    admin_filter = rbac.get_pinecone_filter(admin)
    assert "access_level" in admin_filter
    assert "$in" in admin_filter["access_level"]
    assert len(admin_filter["access_level"]["$in"]) == 3

    editor_filter = rbac.get_pinecone_filter(editor)
    assert len(editor_filter["access_level"]["$in"]) == 2

    viewer_filter = rbac.get_pinecone_filter(viewer)
    assert len(viewer_filter["access_level"]["$in"]) == 1

    print("✓ Pinecone filter generation correct")


def test_permission_logging():
    """Test permission check logging"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    user = rbac.create_user("log_test", "log_key", roles=["viewer"])

    # Perform permission checks with logging
    rbac.check_permission(user, "document", "read", log_check=True)
    rbac.check_permission(user, "document", "write", log_check=True)

    # Verify logs were created
    db = rbac.get_session()
    logs = db.query(rbac_module.PermissionLog).filter(
        rbac_module.PermissionLog.user_id == user.id
    ).all()

    assert len(logs) >= 2
    db.close()
    print("✓ Permission logging works")


def test_permission_stats():
    """Test permission statistics generation"""
    rbac = rbac_module.RBACManager("sqlite:///:memory:")

    user = rbac.create_user("stats_test", "stats_key", roles=["viewer"])

    # Generate some permission checks
    rbac.check_permission(user, "document", "read", log_check=True)
    rbac.check_permission(user, "document", "write", log_check=True)

    # Get stats
    stats = rbac.get_permission_stats(hours=1)

    assert "total_checks" in stats
    assert "denied_count" in stats
    assert stats["total_checks"] >= 2
    print("✓ Permission stats generation works")


def test_app_imports():
    """Test that app.py imports successfully"""
    try:
        # Mock database connection for import
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
            import app
            assert app.app is not None
            print("✓ FastAPI app imports successfully")
    except Exception as e:
        pytest.fail(f"FastAPI app import failed: {e}")


def test_example_data_loads():
    """Test that example data file is valid JSON"""
    import json

    try:
        with open("example_data.json", "r") as f:
            data = json.load(f)

        assert "users" in data
        assert "documents" in data
        assert len(data["users"]) > 0
        assert len(data["documents"]) > 0
        print("✓ Example data is valid JSON")
    except Exception as e:
        pytest.fail(f"Example data loading failed: {e}")


if __name__ == "__main__":
    """Run all smoke tests"""

    print("=" * 60)
    print("Running M6.3 RBAC Smoke Tests")
    print("=" * 60)

    tests = [
        test_config_loads,
        test_access_level_enum,
        test_role_name_enum,
        test_rbac_manager_init_with_sqlite,
        test_user_creation,
        test_api_key_hashing,
        test_user_lookup_by_api_key,
        test_role_assignment,
        test_role_revocation,
        test_permission_checking,
        test_accessible_levels,
        test_pinecone_filter_generation,
        test_permission_logging,
        test_permission_stats,
        test_app_imports,
        test_example_data_loads
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\n{test.__name__}:")
            test()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
