"""CoinGecko API client and data fetching utilities.

This module provides the API client logic for fetching cryptocurrency data
from CoinGecko via PyAirbyte, including retry logic and rate limiting handling.
"""

import logging
import os
import random
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import airbyte as ab
import pendulum

from crypto_elt_pipeline.config import get_config


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""

    pass


def fetch_coingecko_data(
    coin_id: str,
    vs_currency: str,
    days: int,
    logger: logging.Logger,
) -> list[dict]:
    """Fetch raw market data from CoinGecko API via PyAirbyte.

    Implements exponential backoff retry for API failures and rate limits.

    Args:
        coin_id: Cryptocurrency identifier (e.g., 'bitcoin', 'ethereum')
        vs_currency: Target currency for price conversion
        days: Number of days of historical data
        logger: Logger instance for logging

    Returns:
        PyAirbyte message with raw nested API response

    Raises:
        ValueError: If no records are returned from the API
        RateLimitError: If API rate limit is exceeded
    """
    config = get_config()

    # Calculate date range excluding today (only complete days)
    # This ensures consistent record counts across all coins
    yesterday = pendulum.now("UTC").subtract(days=1)
    start_date = yesterday.subtract(days=days - 1).strftime("%d-%m-%Y")
    end_date = yesterday.strftime("%d-%m-%Y")

    # Validate days is one of the allowed values for CoinGecko connector
    allowed_days = ["1", "7", "14", "30", "90", "180", "365", "max"]
    days_str = str(days)
    if days_str not in allowed_days:
        # Round up to nearest allowed value
        days_int = int(days)
        for allowed in ["1", "7", "14", "30", "90", "180", "365", "max"]:
            if allowed == "max" or int(allowed) >= days_int:
                days_str = allowed
                break

    # Add visual formatting to make cryptocurrency processing more distinct
    logger.info(f"{'=' * 60}")
    logger.info(f"🔄 Processing {coin_id.upper()} data")
    logger.info(f"{'=' * 60}")
    logger.debug(f"Date range: {start_date} to {end_date} (excluding today)")

    # Log API key status
    if os.environ.get("COINGECKO_API_KEY"):
        logger.debug("Using CoinGecko Pro API key for higher rate limits")

    def _fetch_with_retry() -> list[dict]:
        """Fetch data with exponential backoff and jitter for rate limits."""
        # Use config values for retry settings
        max_retries = config.ingestion.retry_max_attempts
        base_delay = config.ingestion.retry_base_delay
        max_delay = config.ingestion.retry_max_delay

        for attempt in range(max_retries + 1):
            start_time = time.time()

            try:
                # Build source config with optional API key
                source_config = {
                    "coin_id": coin_id,
                    "vs_currency": vs_currency,
                    "days": days_str,
                    "start_date": start_date,
                    "end_date": end_date,
                }

                # Redirect stdout/stderr to suppress low-level connector noise
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    source = ab.get_source(
                        config.api.connector,
                        docker_image="airbyte/source-coingecko-coins:0.2.26",
                        config=source_config,
                        install_if_missing=True,
                    )
                    source.check()
                    source.select_streams(["market_chart"])
                    records = list(source.get_records("market_chart"))

                if not records:
                    raise ValueError(f"No records found for {coin_id}")

                execution_time = time.time() - start_time
                records_count = len(records)

                logger.info(
                    f"✅ Successfully fetched {records_count} records in {execution_time:.2f}s"
                )

                return records

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e).lower()

                # Log the full error for debugging
                logger.error(f"Airbyte connector error for {coin_id}: {str(e)}")

                # Check for rate limit specific errors
                if any(
                    rate_limit_indicator in error_msg
                    for rate_limit_indicator in [
                        "rate limit",
                        "429",
                        "too many requests",
                        "limit exceeded",
                        "request limit",
                        "api limit",
                        "quota",
                        "throttled",
                    ]
                ):
                    if attempt < max_retries:
                        # Exponential backoff with jitter to avoid thundering herd
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * (0.5 + random.random())  # Add 50-150% jitter
                        logger.warning(
                            f"⚠️ Rate limit hit for {coin_id} (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {jitter:.1f}s before retry..."
                        )
                        time.sleep(jitter)
                        continue
                    else:
                        # Final attempt failed due to rate limit
                        logger.error(f"❌ Failed to fetch data for {coin_id}: Rate limit exceeded.")
                        raise RateLimitError(
                            f"Rate limit exceeded for {coin_id} after {max_retries} attempts"
                        ) from e

                # For other errors, just re-raise the original exception
                raise

    # Execute fetch with retry logic
    return _fetch_with_retry()
