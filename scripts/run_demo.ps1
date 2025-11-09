# Run RBAC demo showcasing core functionality
# Usage: ./scripts/run_demo.ps1

$env:PYTHONPATH = "$PWD/src;$PWD"
python -c "
import sys
sys.path.insert(0, 'src')
from m6_rbac import RBACManager, User, AccessLevel, RoleName

print('=== M6.3 RBAC Demo ===')
print()

# Initialize RBAC Manager with SQLite
rbac = RBACManager('sqlite:///demo.db')
print('✓ RBAC Manager initialized')

# Create users
admin = rbac.create_user('demo_admin', 'admin_key', roles=['admin'])
editor = rbac.create_user('demo_editor', 'editor_key', roles=['editor'])
viewer = rbac.create_user('demo_viewer', 'viewer_key', roles=['viewer'])

print('✓ Created 3 users with different roles')
print()

# Check permissions
print('Permission Checks:')
print(f'  Admin can delete: {rbac.check_permission(admin, \"document\", \"delete\", log_check=False)}')
print(f'  Editor can write: {rbac.check_permission(editor, \"document\", \"write\", log_check=False)}')
print(f'  Editor can delete: {rbac.check_permission(editor, \"document\", \"delete\", log_check=False)}')
print(f'  Viewer can read: {rbac.check_permission(viewer, \"document\", \"read\", log_check=False)}')
print(f'  Viewer can write: {rbac.check_permission(viewer, \"document\", \"write\", log_check=False)}')
print()

# Show access levels
print('Document Access Levels:')
print(f'  Admin: {rbac.get_accessible_levels(admin)}')
print(f'  Editor: {rbac.get_accessible_levels(editor)}')
print(f'  Viewer: {rbac.get_accessible_levels(viewer)}')
print()

print('Demo complete!')
"
