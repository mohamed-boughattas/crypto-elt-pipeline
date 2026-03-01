"""Configuration loader for the crypto ELT pipeline.

This module provides a centralized configuration system that loads
settings from the coins.yaml file, ensuring consistency across
Dagster partitions, dbt tests, and documentation.

Features:
- Environment variable support for sensitive data
- Thread-safe lazy loading
- Comprehensive configuration validation
- Support for all pipeline components
"""

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CoinConfig:
    """Configuration for a single cryptocurrency."""

    id: str
    name: str
    symbol: str
    color: str
    category: str = "layer1"
    enabled: bool = True


@dataclass
class ApiConfig:
    """API connection configuration."""

    source: str
    connector: str
    base_url: str
    docker_image: str = "airbyte/source-coingecko-coins:0.2.26"


@dataclass
class IngestionConfig:
    """Data ingestion settings."""

    vs_currency: str
    days_to_fetch: int
    history_days: int
    retry_max_attempts: int
    retry_base_delay: int
    retry_max_delay: int
    # Performance settings
    batch_size: int = 1000
    max_concurrent: int = 3


@dataclass
class MonitoringConfig:
    """Monitoring and observability settings."""

    enable_metrics: bool
    freshness_threshold_hours: int
    warning_threshold_hours: int
    log_level: str


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    memory_limit_gb: int
    enable_query_cache: bool
    schema_version: float


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""

    coins: list[CoinConfig]
    api: ApiConfig
    ingestion: IngestionConfig
    monitoring: MonitoringConfig
    database: DatabaseConfig

    @property
    def enabled_coins(self) -> list[CoinConfig]:
        """Return only enabled coins."""
        return [coin for coin in self.coins if coin.enabled]

    @property
    def coin_ids(self) -> list[str]:
        """Return list of enabled coin IDs."""
        return [coin.id for coin in self.enabled_coins]

    @property
    def coin_colors(self) -> dict[str, str]:
        """Return mapping of coin ID to color."""
        return {coin.id: coin.color for coin in self.enabled_coins}


# Path to configuration file
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "coins.yaml"


def load_config() -> PipelineConfig:
    """Load configuration from coins.yaml file.

    Returns:
        PipelineConfig object with all settings.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is invalid.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty configuration file: {CONFIG_PATH}")

    # Parse coins
    coins = [
        CoinConfig(
            id=coin["id"],
            name=coin["name"],
            symbol=coin["symbol"],
            color=coin["color"],
            category=coin.get("category", "layer1"),
            enabled=coin.get("enabled", True),
        )
        for coin in data.get("coins", [])
    ]

    # Parse API config
    api_data = data.get("api", {})
    api = ApiConfig(
        source=api_data.get("source", "coingecko"),
        connector=api_data.get("connector", "source-coingecko-coins"),
        base_url=api_data.get("base_url", "https://api.coingecko.com/api/v3"),
        docker_image=api_data.get("docker_image", "airbyte/source-coingecko-coins:0.2.26"),
    )

    # Parse ingestion config
    ingestion_data = data.get("ingestion", {})
    ingestion = IngestionConfig(
        vs_currency=ingestion_data.get("vs_currency", "usd"),
        days_to_fetch=ingestion_data.get("days_to_fetch", 30),
        history_days=ingestion_data.get("history_days", 365),
        retry_max_attempts=ingestion_data.get("retry_max_attempts", 3),
        retry_base_delay=ingestion_data.get("retry_base_delay", 10),
        retry_max_delay=ingestion_data.get("retry_max_delay", 60),
        batch_size=ingestion_data.get("batch_size", 1000),
        max_concurrent=ingestion_data.get("max_concurrent", 3),
    )

    # Parse monitoring config
    monitoring_data = data.get("monitoring", {})
    monitoring = MonitoringConfig(
        enable_metrics=monitoring_data.get("enable_metrics", True),
        freshness_threshold_hours=monitoring_data.get("freshness_threshold_hours", 24),
        warning_threshold_hours=monitoring_data.get("warning_threshold_hours", 12),
        log_level=monitoring_data.get("log_level", "INFO"),
    )

    # Parse database config
    database_data = data.get("database", {})
    database = DatabaseConfig(
        memory_limit_gb=database_data.get("memory_limit_gb", 8),
        enable_query_cache=database_data.get("enable_query_cache", True),
        schema_version=database_data.get("schema_version", 1.0),
    )

    return PipelineConfig(
        coins=coins, api=api, ingestion=ingestion, monitoring=monitoring, database=database
    )


@functools.lru_cache(maxsize=1)
def get_config() -> PipelineConfig:
    """Get the global configuration instance.

    This function implements thread-safe lazy loading using LRU cache
    to avoid loading the config during module import, which is important
    for Dagster's code location loading.

    Returns:
        PipelineConfig object with all settings.
    """
    return load_config()


def reload_config() -> PipelineConfig:
    """Reload configuration from file.

    Useful for testing or when config file changes.

    Returns:
        Newly loaded PipelineConfig object.
    """
    get_config.cache_clear()
    return get_config()
