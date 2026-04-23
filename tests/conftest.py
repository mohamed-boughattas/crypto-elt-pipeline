"""Shared pytest fixtures for all tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import pendulum
import polars as pl
import pytest


@pytest.fixture
def temp_db_path():
    """Provide a temporary DuckDB database path."""
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(path)
    yield Path(path)
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def crypto_db_with_data(temp_db_path):
    """Populate a temp DuckDB with raw.crypto_prices data for testing."""
    rows = [
        (
            "bitcoin",
            "usd",
            pendulum.now("UTC"),
            pendulum.datetime(2026, 3, 15, 10, 0, 0),
            67000.0,
            1.3e12,
            1e11,
        ),
        (
            "bitcoin",
            "usd",
            pendulum.now("UTC"),
            pendulum.datetime(2026, 3, 15, 11, 0, 0),
            67100.0,
            1.31e12,
            1.1e11,
        ),
        (
            "bitcoin",
            "usd",
            pendulum.now("UTC"),
            pendulum.datetime(2026, 3, 15, 12, 0, 0),
            67200.0,
            1.32e12,
            1.2e11,
        ),
        (
            "ethereum",
            "usd",
            pendulum.now("UTC"),
            pendulum.datetime(2026, 3, 15, 10, 0, 0),
            3500.0,
            4e11,
            5e10,
        ),
    ]
    schema = {
        "coin": pl.String,
        "currency": pl.String,
        "ingested_at": pl.Datetime,
        "recorded_at": pl.Datetime,
        "price": pl.Float64,
        "market_cap": pl.Float64,
        "volume": pl.Float64,
    }
    df = pl.DataFrame(rows, schema=schema, orient="row")
    conn = duckdb.connect(str(temp_db_path))
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute("CREATE TABLE raw.crypto_prices AS SELECT * FROM df")
    del df
    conn.close()

    return temp_db_path


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


@pytest.fixture(autouse=True)
def mock_airbyte_source():
    """Mock PyAirbyte source to avoid real API calls in tests.

    This fixture automatically mocks the airbyte.get_source function
    to prevent tests from making real API calls to CoinGecko, which
    could hit rate limits in CI environments.
    """
    mock_source = MagicMock()
    mock_source.check.return_value = None
    mock_source.select_streams.return_value = None
    mock_source.get_records.return_value = iter(
        [
            {
                "prices": [[[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]]],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0], [1700003600000.0, 852000000000.0]]
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0], [1700003600000.0, 25500000000.0]]
                ],
            }
        ]
    )

    with patch("airbyte.get_source", return_value=mock_source):
        yield mock_source
