"""
Smoke tests for Secrets Management & Rotation module.

These tests verify basic functionality without requiring external services.
Network calls are gracefully skipped if Vault is not available.

Run with:
    pytest tests/test_smoke.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from m6_secrets.config import AppConfig, VaultConfig, get_clients
from m6_secrets.core import (
    VaultClient,
    ResilientVaultClient,
    SecretRotationManager,
    validate_environment_config,
    create_gitignore_for_secrets
)


class TestConfig:
    """Test configuration loading and validation."""

    def test_vault_config_defaults(self):
        """Test VaultConfig uses correct defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = VaultConfig()
            assert config.addr == "http://localhost:8200"
            assert config.mount_point == "secret"
            assert not config.is_configured()  # No token

    def test_vault_config_from_env(self):
        """Test VaultConfig loads from environment variables."""
        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault.example.com:8200",
            "VAULT_TOKEN": "test-token-123",
            "VAULT_MOUNT_POINT": "custom"
        }):
            config = VaultConfig()
            assert config.addr == "http://vault.example.com:8200"
            assert config.token == "test-token-123"
            assert config.mount_point == "custom"
            assert config.is_configured()

    def test_app_config_defaults(self):
        """Test AppConfig uses correct defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = AppConfig()
            assert config.environment == "dev"
            assert config.enable_rotation is True
            assert config.enable_metrics is True
            assert config.fallback_to_env is True

    def test_app_config_invalid_environment(self):
        """Test AppConfig rejects invalid environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "invalid"}):
            with pytest.raises(ValueError, match="Invalid ENVIRONMENT"):
                AppConfig()

    def test_app_config_production_validation(self):
        """Test AppConfig validates production requirements."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "prod",
            "VAULT_TOKEN": "dev-root-token"
        }):
            with pytest.raises(ValueError, match="dev-root-token detected in production"):
                AppConfig()


class TestVaultClient:
    """Test VaultClient functionality."""

    def test_vault_client_init_no_token(self):
        """Test VaultClient raises error if token not provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="VAULT_TOKEN must be provided"):
                VaultClient()

    @patch('hvac.Client')
    def test_vault_client_init_success(self, mock_hvac_client):
        """Test VaultClient initializes successfully with valid token."""
        # Mock successful authentication
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = True
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            client = VaultClient(environment="dev")
            assert client.environment == "dev"
            assert client.vault_token == "test-token"

    @patch('hvac.Client')
    def test_vault_client_auth_failure(self, mock_hvac_client):
        """Test VaultClient raises error if authentication fails."""
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = False
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "invalid-token"}):
            with pytest.raises(ConnectionError, match="Failed to authenticate"):
                VaultClient()

    @patch('hvac.Client')
    def test_vault_client_get_secret(self, mock_hvac_client):
        """Test VaultClient.get_secret returns expected data."""
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = True
        mock_client_instance.secrets.kv.v2.read_secret_version.return_value = {
            'data': {
                'data': {
                    'openai_key': 'sk-test-123',
                    'pinecone_key': 'pinecone-test-456'
                }
            }
        }
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            client = VaultClient(environment="dev")
            secrets = client.get_secret("rag-system/dev")

            assert 'openai_key' in secrets
            assert secrets['openai_key'] == 'sk-test-123'


class TestResilientVaultClient:
    """Test ResilientVaultClient with fallback logic."""

    @patch('hvac.Client')
    def test_resilient_client_vault_unavailable_fallback(self, mock_hvac_client):
        """Test ResilientVaultClient falls back to env vars if Vault unavailable."""
        # Mock Vault connection failure
        mock_hvac_client.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {
            "VAULT_TOKEN": "test-token",
            "OPENAI_API_KEY": "sk-fallback-key",
            "PINECONE_API_KEY": "pinecone-fallback-key"
        }):
            client = ResilientVaultClient(
                environment="dev",
                max_retries=1,
                fallback_env=True
            )

            # Should not raise, but fall back to env vars
            secrets = client.get_secret("rag-system/dev")
            assert secrets['openai_key'] == 'sk-fallback-key'

    @patch('hvac.Client')
    def test_resilient_client_no_fallback_raises(self, mock_hvac_client):
        """Test ResilientVaultClient raises if fallback disabled."""
        mock_hvac_client.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            with pytest.raises(ConnectionError, match="Failed to connect to Vault"):
                ResilientVaultClient(
                    environment="dev",
                    max_retries=1,
                    fallback_env=False
                )


class TestSecretRotationManager:
    """Test SecretRotationManager functionality."""

    @patch('hvac.Client')
    def test_rotation_manager_init(self, mock_hvac_client):
        """Test SecretRotationManager initializes correctly."""
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = True
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            vault_client = VaultClient()
            manager = SecretRotationManager(vault_client)

            assert manager.active_requests == 0
            assert not manager.rotation_in_progress.is_set()

    @patch('hvac.Client')
    def test_rotation_manager_track_request(self, mock_hvac_client):
        """Test request tracking context manager."""
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = True
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            vault_client = VaultClient()
            manager = SecretRotationManager(vault_client)

            assert manager.active_requests == 0

            with manager.track_request():
                assert manager.active_requests == 1

            assert manager.active_requests == 0


class TestUtilityFunctions:
    """Test utility functions."""

    def test_validate_environment_config_valid(self):
        """Test environment validation accepts valid environments."""
        assert validate_environment_config("dev") is True
        assert validate_environment_config("staging") is True
        assert validate_environment_config("prod") is True

    def test_validate_environment_config_invalid(self):
        """Test environment validation rejects invalid environments."""
        with pytest.raises(ValueError, match="Invalid ENVIRONMENT"):
            validate_environment_config("invalid")

    def test_validate_environment_config_prod_no_token(self):
        """Test production validation requires VAULT_TOKEN."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="VAULT_TOKEN required"):
                validate_environment_config("prod")

    def test_create_gitignore_for_secrets(self, tmp_path):
        """Test gitignore creation."""
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            result = create_gitignore_for_secrets()
            assert result is True

            # Check .gitignore was created/updated
            gitignore_path = tmp_path / ".gitignore"
            assert gitignore_path.exists()

            content = gitignore_path.read_text()
            assert ".env" in content
            assert "vault-token" in content
            assert ".secrets.baseline" in content

        finally:
            os.chdir(original_cwd)


class TestGetClients:
    """Test get_clients() function."""

    def test_get_clients_no_vault_config(self):
        """Test get_clients returns empty dict if Vault not configured."""
        with patch.dict(os.environ, {}, clear=True):
            clients = get_clients()
            assert isinstance(clients, dict)
            assert len(clients) == 0

    @patch('hvac.Client')
    def test_get_clients_vault_configured(self, mock_hvac_client):
        """Test get_clients initializes Vault client if configured."""
        mock_client_instance = MagicMock()
        mock_client_instance.is_authenticated.return_value = True
        mock_client_instance.secrets.kv.v2.read_secret_version.return_value = {
            'data': {
                'data': {
                    'openai_key': 'sk-test-123',
                    'pinecone_key': 'pinecone-test-456'
                }
            }
        }
        mock_hvac_client.return_value = mock_client_instance

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            with patch('config.OpenAI'), patch('config.Pinecone'):
                clients = get_clients()
                assert 'vault' in clients


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
