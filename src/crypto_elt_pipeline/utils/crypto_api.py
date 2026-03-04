"""CoinGecko API client and data fetching utilities.

This module provides API client logic for fetching cryptocurrency data
from CoinGecko via PyAirbyte, including retry logic and rate limiting handling.
"""

import logging
import os
import random
import time
from contextlib import redirect_stderr, redirect_stdout

import airbyte as ab
import pendulum

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import LOGS_DIR


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

    # Validate days is one of allowed values for CoinGecko connector
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

                # Redirect PyAirbyte connector output to log file instead of suppressing
                # This preserves debugging information while keeping console clean
                airbyte_log_path = LOGS_DIR / "airbyte_connector.log"
                airbyte_log_path.parent.mkdir(parents=True, exist_ok=True)

                with (
                    open(airbyte_log_path, "a") as log_file,
                    redirect_stdout(log_file),
                    redirect_stderr(log_file),
                ):
                    source = ab.get_source(
                        config.api.connector,
                        docker_image=config.api.docker_image,
                        config=source_config,
                        install_if_missing=True,
                    )
                    source.check()
                    source.select_streams(["market_chart"])
                    records = list(source.get_records("market_chart"))

                if not records:
                    # Empty response - treat as transient error and retry
                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * (0.5 + random.random())
                        logger.warning(
                            f"⚠️ Empty response for {coin_id} (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Waiting {jitter:.1f}s before retry..."
                        )
                        time.sleep(jitter)
                        continue
                    else:
                        raise ValueError(
                            f"No records found for {coin_id} after {max_retries} attempts"
                        )

                execution_time = time.time() - start_time
                records_count = len(records)

                logger.info(
                    f"✅ Successfully fetched {records_count} records in {execution_time:.2f}s"
                )

                return records

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e).lower()

                # Log full error for debugging
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

                # For other errors, provide more specific error messages and graceful degradation
                if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * (0.5 + random.random())
                        logger.warning(
                            f"⚠️ Network/connection error for {coin_id} (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {jitter:.1f}s before retry..."
                        )
                        time.sleep(jitter)
                        continue
                    else:
                        logger.error(
                            f"❌ Network error for {coin_id}: Unable to connect to API after {max_retries} attempts"
                        )
                        raise ConnectionError(
                            f"Unable to connect to CoinGecko API for {coin_id} after {max_retries} attempts"
                        ) from e

                elif "invalid" in error_msg or "not found" in error_msg or "404" in error_msg:
                    logger.error(f"❌ Invalid coin ID or data not available for {coin_id}")
                    raise ValueError(f"Invalid coin ID '{coin_id}' or data not available") from e

                elif "docker" in error_msg or "container" in error_msg:
                    logger.error(f"❌ Docker/container error for {coin_id}: {str(e)}")
                    raise RuntimeError(
                        f"Docker container error for {coin_id}. Please check Docker is running and connector is available."
                    ) from e

                elif "memory" in error_msg or "out of memory" in error_msg:
                    logger.error(f"❌ Memory error for {coin_id}: {str(e)}")
                    raise MemoryError(
                        f"Insufficient memory to process {coin_id} data. Try reducing batch size or available memory."
                    ) from e

                else:
                    # Generic error with detailed context
                    logger.error(
                        f"❌ Unexpected error for {coin_id} (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                    )
                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * (0.5 + random.random())
                        logger.warning(f"Waiting {jitter:.1f}s before retry...")
                        time.sleep(jitter)
                        continue
                    else:
                        raise RuntimeError(
                            f"Failed to fetch data for {coin_id} after {max_retries + 1} attempts. "
                            f"Last error: {str(e)}"
                        ) from e

        # This should never be reached but satisfies pyright
        raise ValueError(f"Unexpected error fetching data for {coin_id}")

    # Execute fetch with retry logic
    return _fetch_with_retry()  # type: ignore[return]
