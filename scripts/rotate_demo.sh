#!/bin/bash
# Demonstrate secret rotation functionality
# Usage: bash scripts/rotate_demo.sh

echo -e "\033[36mSecret Rotation Demo\033[0m"
echo -e "\033[36m===================\033[0m"
echo ""

# Set Python path to include src directory
export PYTHONPATH="$PWD/src:$PWD"

# Check if Vault is configured
if [ -z "$VAULT_TOKEN" ]; then
    echo -e "\033[33mWarning: VAULT_TOKEN not set. Demo will use fallback mode.\033[0m"
    echo -e "\033[33mTo use Vault, set: export VAULT_TOKEN='dev-root-token'\033[0m"
    echo ""
fi

# Run the demo
python3 -c "
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
"
