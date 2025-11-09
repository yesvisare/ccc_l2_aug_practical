# Demonstrate secret rotation functionality
# Usage: powershell scripts/rotate_demo.ps1

Write-Host "Secret Rotation Demo" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan
Write-Host ""

# Set Python path to include src directory
$env:PYTHONPATH = "$PWD/src;$PWD"

# Check if Vault is configured
if (-not $env:VAULT_TOKEN) {
    Write-Host "Warning: VAULT_TOKEN not set. Demo will use fallback mode." -ForegroundColor Yellow
    Write-Host "To use Vault, set: `$env:VAULT_TOKEN='dev-root-token'" -ForegroundColor Yellow
    Write-Host ""
}

# Run the demo
python -c @"
from m6_secrets.core import VaultClient, SecretRotationManager
from m6_secrets.config import AppConfig
import os

print('Initializing configuration...')
try:
    config = AppConfig()
    print(f'Environment: {config.environment}')
    print(f'Vault configured: {config.vault.is_configured()}')
    print('')

    if config.vault.is_configured():
        print('Initializing Vault client...')
        vault = VaultClient(environment=config.environment)
        print('✓ Vault client initialized')

        print('Initializing rotation manager...')
        rotation_mgr = SecretRotationManager(vault)
        print('✓ Rotation manager initialized')
        print('')

        print('Rotation capabilities:')
        print(f'  - Active requests: {rotation_mgr.active_requests}')
        print(f'  - Rotation in progress: {rotation_mgr.rotation_in_progress.is_set()}')
        print('')
        print('✓ Rotation demo complete!')
    else:
        print('⚠ Vault not configured - skipping rotation demo')
        print('Set VAULT_ADDR and VAULT_TOKEN to test rotation')

except Exception as e:
    print(f'❌ Demo failed: {e}')
"@
