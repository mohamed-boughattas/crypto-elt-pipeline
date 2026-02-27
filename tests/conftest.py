"""Shared pytest fixtures for all tests.

This module provides reusable test fixtures to eliminate duplicated
DataFrame construction across test modules.
"""

import pendulum
import polars as pl
import pytest


@pytest.fixture
def sample_raw_market_data():
    """Standard raw CoinGecko response for testing.

    Returns:
        Polars DataFrame with nested market data structure from CoinGecko API.
    """
    return pl.DataFrame(
        {
            "prices": [
                [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
            ],
            "market_caps": [
                [
                    [1700000000000.0, 850000000000.0],
                    [1700003600000.0, 852000000000.0],
                ],
            ],
            "total_volumes": [
                [
                    [1700000000000.0, 25000000000.0],
                    [1700003600000.0, 25500000000.0],
                ],
            ],
        },
        strict=False,
    )


@pytest.fixture
def sample_raw_market_data_multi_row():
    """Raw CoinGecko response with multiple rows for testing.

    Returns:
        Polars DataFrame with multiple rows of nested market data.
    """
    return pl.DataFrame(
        {
            "prices": [
                [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
                [[1700007200000.0, 45200.00]],
            ],
            "market_caps": [
                [
                    [1700000000000.0, 850000000000.0],
                    [1700003600000.0, 852000000000.0],
                ],
                [[1700007200000.0, 853000000000.0]],
            ],
            "total_volumes": [
                [
                    [1700000000000.0, 25000000000.0],
                    [1700003600000.0, 25500000000.0],
                ],
                [[1700007200000.0, 26000000000.0]],
            ],
        },
        strict=False,
    )


@pytest.fixture
def sample_bronze_data():
    """Bronze layer data with metadata columns added.

    Returns:
        Polars DataFrame simulating the output of the crypto_prices asset.
    """
    return pl.DataFrame(
        {
            "coin": ["bitcoin", "bitcoin", "bitcoin"],
            "currency": ["usd", "usd", "usd"],
            "ingested_at": [
                pendulum.datetime(2024, 1, 1, 12, 0, 0),
                pendulum.datetime(2024, 1, 1, 12, 0, 0),
                pendulum.datetime(2024, 1, 1, 12, 0, 0),
            ],
            "recorded_at": [
                pendulum.datetime(2024, 1, 1, 0, 0, 0),
                pendulum.datetime(2024, 1, 1, 1, 0, 0),
                pendulum.datetime(2024, 1, 1, 2, 0, 0),
            ],
            "price": [45000.50, 45100.25, 45200.00],
            "market_cap": [850000000000.0, 852000000000.0, 853000000000.0],
            "volume": [25000000000.0, 25500000000.0, 26000000000.0],
        },
        strict=False,
    )


@pytest.fixture
def sample_silver_data():
    """Silver layer data after flattening and cleaning.

    Returns:
        Polars DataFrame simulating the output of stg_crypto_prices dbt model.
    """
    return pl.DataFrame(
        {
            "coin": ["bitcoin", "bitcoin", "bitcoin"],
            "currency": ["usd", "usd", "usd"],
            "recorded_at": [
                pendulum.datetime(2024, 1, 1, 0, 0, 0),
                pendulum.datetime(2024, 1, 1, 1, 0, 0),
                pendulum.datetime(2024, 1, 1, 2, 0, 0),
            ],
            "price": [45000.50, 45100.25, 45200.00],
            "market_cap": [850000000000.0, 852000000000.0, 853000000000.0],
            "volume": [25000000000.0, 25500000000.0, 26000000000.0],
        }
    )


@pytest.fixture
def sample_gold_data():
    """Gold layer OHLC candlestick data.

    Returns:
        Polars DataFrame simulating the output of fct_crypto_candlesticks dbt model.
    """
    return pl.DataFrame(
        {
            "trade_date": pl.date_range(
                pendulum.datetime(2024, 1, 1), pendulum.datetime(2024, 1, 31), eager=True
            ),
            "coin": ["bitcoin"] * 31,
            "open_price": [45000.0 + i * 100 for i in range(31)],
            "high_price": [45500.0 + i * 100 for i in range(31)],
            "low_price": [44500.0 + i * 100 for i in range(31)],
            "close_price": [45200.0 + i * 100 for i in range(31)],
            "daily_volume": [25000000000.0] * 31,
            "volatility_pct": [2.5] * 31,
            "samples_count": [24] * 31,
            "sma_7": [45100.0 + i * 50 for i in range(31)],
            "sma_25": [45050.0 + i * 30 for i in range(31)],
        }
    )


@pytest.fixture
def sample_multi_coin_gold_data():
    """Gold layer data with multiple cryptocurrencies.

    Returns:
        Polars DataFrame with multiple coins for testing multi-coin scenarios.
    """
    dates = pl.date_range(pendulum.datetime(2024, 1, 1), pendulum.datetime(2024, 1, 10), eager=True)
    coins = ["bitcoin", "ethereum", "solana"]

    data = []
    for coin in coins:
        for i, date in enumerate(dates):
            base_price = 45000.0 if coin == "bitcoin" else 2500.0 if coin == "ethereum" else 100.0
            data.append(
                {
                    "trade_date": date,
                    "coin": coin,
                    "open_price": base_price + i * 10,
                    "high_price": base_price + i * 10 + 50,
                    "low_price": base_price + i * 10 - 50,
                    "close_price": base_price + i * 10 + 20,
                    "daily_volume": 25000000000.0 if coin == "bitcoin" else 15000000000.0,
                    "volatility_pct": 2.5,
                    "samples_count": 24,
                }
            )

    return pl.DataFrame(data)
