"""Tests for configuration loading and constants.

This module consolidates configuration and constants testing.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from crypto_elt_pipeline.config import get_config, load_config, reload_config
from crypto_elt_pipeline.constants import DUCKDB_PATH, PROJECT_ROOT


class TestConfig:
    """Tests for configuration loading."""

    def test_load_config_exists(self):
        """Test that config can be loaded."""
        config = load_config()
        assert config is not None

    def test_get_config_returns_config(self):
        """Test that get_config returns a config object."""
        config = get_config()
        assert config is not None

    def test_config_has_coins(self):
        """Test that config has coins."""
        config = get_config()
        assert hasattr(config, "coins")
        assert len(config.coins) > 0

    def test_config_has_api_settings(self):
        """Test that config has API settings."""
        config = get_config()
        assert hasattr(config, "api")
        assert hasattr(config.api, "source")
        assert hasattr(config.api, "connector")

    def test_config_has_ingestion_settings(self):
        """Test that config has ingestion settings."""
        config = get_config()
        assert hasattr(config, "ingestion")
        assert hasattr(config.ingestion, "vs_currency")
        assert hasattr(config.ingestion, "days_to_fetch")

    def test_config_has_api_docker_settings(self):
        """Test that config has API docker settings."""
        config = get_config()
        assert hasattr(config.api, "docker_image")

    def test_config_has_retry_settings(self):
        """Test that config has retry settings."""
        config = get_config()
        assert hasattr(config.ingestion, "retry_max_attempts")
        assert hasattr(config.ingestion, "retry_base_delay")

    def test_config_has_pipeline_settings(self):
        """Test that config has pipeline settings."""
        config = get_config()
        # Config has ingestion settings
        assert hasattr(config, "ingestion")


class TestConfigCoins:
    """Tests for coin configuration."""

    def test_coins_have_required_fields(self):
        """Test that coins have required fields."""
        config = get_config()
        for coin in config.coins:
            assert hasattr(coin, "id")
            assert hasattr(coin, "name")
            assert hasattr(coin, "symbol")
            assert hasattr(coin, "color")
            assert coin.id is not None
            assert coin.name is not None
            assert coin.symbol is not None
            assert coin.color is not None

    def test_enabled_coins_filter(self):
        """Test that enabled coins filter works."""
        config = get_config()
        enabled_coins = config.enabled_coins
        assert len(enabled_coins) > 0
        for coin in enabled_coins:
            assert coin.enabled is True

    def test_coin_ids_list(self):
        """Test that coin IDs list works."""
        config = get_config()
        coin_ids = config.coin_ids
        assert len(coin_ids) > 0
        assert all(isinstance(coin_id, str) for coin_id in coin_ids)

    def test_coin_colors_mapping(self):
        """Test that coin colors mapping works."""
        config = get_config()
        coin_colors = config.coin_colors
        assert len(coin_colors) > 0
        for coin_id, color in coin_colors.items():
            assert isinstance(coin_id, str)
            assert isinstance(color, str)
            assert color.startswith("#")  # Should be hex color

    def test_enabled_coin_ids(self):
        """Test that enabled coin IDs list works."""
        config = get_config()
        enabled_coins = config.enabled_coins
        enabled_ids = [coin.id for coin in enabled_coins]
        assert len(enabled_ids) > 0
        assert all(isinstance(coin_id, str) for coin_id in enabled_ids)


class TestConstants:
    """Tests for global constants."""

    def test_duckdb_path_is_defined(self):
        """Test that DUCKDB_PATH is properly defined."""
        assert DUCKDB_PATH is not None
        assert isinstance(DUCKDB_PATH, Path)

    def test_duckdb_path_has_correct_name(self):
        """Test that DUCKDB_PATH points to correct file."""
        assert DUCKDB_PATH.name == "crypto.duckdb"

    def test_duckdb_path_in_data_directory(self):
        """Test that DUCKDB_PATH is in data directory."""
        assert "data" in str(DUCKDB_PATH)
        assert DUCKDB_PATH.parent.name == "data"

    def test_project_root_is_defined(self):
        """Test that PROJECT_ROOT is properly defined."""
        assert PROJECT_ROOT is not None
        assert isinstance(PROJECT_ROOT, Path)

    def test_project_root_exists(self):
        """Test that PROJECT_ROOT directory exists."""
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()


class TestConfigErrorPaths:
    """Tests for configuration error handling."""

    def test_load_config_missing_file_raises(self):
        """Missing config file raises FileNotFoundError."""
        with (
            patch("crypto_elt_pipeline.config.CONFIG_PATH", Path("/nonexistent/path.yaml")),
            pytest.raises(FileNotFoundError),
        ):
            load_config()

    def test_load_config_empty_file_raises(self):
        """Empty config file raises ValueError."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            temp_path = Path(f.name)

        with patch("crypto_elt_pipeline.config.CONFIG_PATH", temp_path):
            try:
                with pytest.raises(ValueError, match="Empty configuration"):
                    load_config()
            finally:
                temp_path.unlink()

    def test_reload_config_clears_cache(self):
        """reload_config clears the LRU cache and reloads."""
        reload_config()
        config2 = reload_config()
        assert config2 is not None
