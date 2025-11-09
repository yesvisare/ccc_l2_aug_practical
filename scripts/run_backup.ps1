# M5.4 Vector Index Management - Backup Runner (Windows PowerShell)
#
# Usage: .\scripts\run_backup.ps1
#
# This script demonstrates backup readiness by importing the core module.

# Set PYTHONPATH to include src/ directory
$env:PYTHONPATH = "$PWD/src"

Write-Host "=== M5.4 Backup System Check ===" -ForegroundColor Green
Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Cyan
Write-Host ""

# Test that the backup manager can be imported and is ready
python -c @"
from m5_4_vector_index.core import IndexBackupManager
from m5_4_vector_index.config import Config, get_clients

print('✓ IndexBackupManager imported successfully')
print('✓ Config module loaded')

clients = get_clients()
if clients['s3']:
    print('✓ S3 client available - backup functionality ready')
else:
    print('⚠ S3 client unavailable - set AWS credentials to enable backups')

print('')
print('Backup system ready. Example usage:')
print('  from m5_4_vector_index import IndexBackupManager, Config, get_clients')
print('  clients = get_clients()')
print('  backup_mgr = IndexBackupManager(clients[\"pinecone\"], clients[\"s3\"], Config.S3_BACKUP_BUCKET)')
print('  metadata = backup_mgr.backup_index(\"my-index\")')
"@

Write-Host ""
Write-Host "Backup check complete." -ForegroundColor Green
