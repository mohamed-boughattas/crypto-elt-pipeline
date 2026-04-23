"""Configuration loader for the crypto ELT pipeline.

This module provides a centralized configuration system that loads
settings from the coins.yaml file, ensuring consistency across
Dagster partitions, dbt tests, and documentation.
"""

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CoinConfig:
    id: str
    name: str
    symbol: str
    color: str
    category: str = "layer1"
    enabled: bool = True


@dataclass
class ApiConfig:
    source: str
    connector: str
    base_url: str
    docker_image: str = "airbyte/source-coingecko-coins:0.2.26"


@dataclass
class IngestionConfig:
    vs_currency: str
    days_to_fetch: int
    history_days: int
    retry_max_attempts: int
    retry_base_delay: int
    retry_max_delay: int
    batch_size: int = 1000
    max_concurrent: int = 3


@dataclass
class PipelineConfig:
    coins: list[CoinConfig]
    api: ApiConfig
    ingestion: IngestionConfig

    @property
    def enabled_coins(self) -> list[CoinConfig]:
        return [coin for coin in self.coins if coin.enabled]

    @property
    def coin_ids(self) -> list[str]:
        return [coin.id for coin in self.enabled_coins]

    @property
    def coin_colors(self) -> dict[str, str]:
        return {coin.id: coin.color for coin in self.enabled_coins}


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "coins.yaml"


def load_config() -> PipelineConfig:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty configuration file: {CONFIG_PATH}")

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

    api_data = data.get("api", {})
    api = ApiConfig(
        source=api_data.get("source", "coingecko"),
        connector=api_data.get("connector", "source-coingecko-coins"),
        base_url=api_data.get("base_url", "https://api.coingecko.com/api/v3"),
        docker_image=api_data.get("docker_image", "airbyte/source-coingecko-coins:0.2.26"),
    )

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

    return PipelineConfig(coins=coins, api=api, ingestion=ingestion)


@functools.lru_cache(maxsize=1)
def get_config() -> PipelineConfig:
    return load_config()


def reload_config() -> PipelineConfig:
    get_config.cache_clear()
    return get_config()
