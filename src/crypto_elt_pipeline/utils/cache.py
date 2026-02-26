"""Caching utilities for the crypto ELT pipeline.

This module provides caching mechanisms to improve performance by avoiding
redundant API calls and expensive computations.
"""

import hashlib
import json
import pickle
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pendulum

from crypto_elt_pipeline.constants import DUCKDB_PATH

T = TypeVar("T")


class SimpleCache:
    """Simple file-based cache with TTL support."""

    def __init__(self, cache_dir: Path, default_ttl_hours: int = 1):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl_hours: Default time-to-live in hours
        """
        self.cache_dir = cache_dir
        self.default_ttl_hours = default_ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a cache key hash."""
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get the full path for a cache file."""
        cache_key = self._get_cache_key(key)
        return self.cache_dir / f"{cache_key}.cache"

    def get(self, key: str) -> Any | None:
        """Get a value from cache if it exists and is not expired.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)

            # Check if expired
            if time.time() - data["timestamp"] > data["ttl_seconds"]:
                cache_path.unlink()  # Remove expired cache
                return None

            return data["value"]

        except (pickle.PickleError, EOFError, KeyError):
            # Remove corrupted cache file
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: Any, ttl_hours: int | None = None) -> None:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_hours: Time-to-live in hours (uses default if None)
        """
        cache_path = self._get_cache_path(key)
        ttl_seconds = (ttl_hours or self.default_ttl_hours) * 3600

        data = {
            "value": value,
            "timestamp": time.time(),
            "ttl_seconds": ttl_seconds,
        }

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
        except pickle.PickleError:
            # If pickling fails, don't cache
            pass

    def delete(self, key: str) -> bool:
        """Delete a cache entry.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(key)
        try:
            cache_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink(missing_ok=True)


def cache_result(
    cache: SimpleCache,
    key_func: Callable[..., str] | None = None,
    ttl_hours: int | None = None,
):
    """Decorator to cache function results.

    Args:
        cache: Cache instance
        key_func: Function to generate cache key from arguments
        ttl_hours: Time-to-live in hours

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_data = {
                    "func": func.__name__,
                    "args": args,
                    "kwargs": kwargs,
                }
                cache_key = json.dumps(key_data, sort_keys=True, default=str)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_hours)
            return result

        return wrapper

    return decorator


# Global cache instance
CACHE_DIR = DUCKDB_PATH.parent / ".cache"
cache = SimpleCache(CACHE_DIR, default_ttl_hours=2)


def get_cache_key_for_api(
    coin_id: str,
    vs_currency: str,
    days: int,
    context: Any,
) -> str:
    """Generate cache key for API requests.

    Args:
        coin_id: Cryptocurrency identifier
        vs_currency: Target currency
        days: Number of days
        context: Execution context (used to derive date range)

    Returns:
        Cache key string
    """
    # Calculate the date range based on days
    end_date = pendulum.now("UTC").date()
    start_date = pendulum.now("UTC").subtract(days=days).date()
    return f"api_{coin_id}_{vs_currency}_{days}_{start_date}_{end_date}"


def get_cache_key_for_unnest(
    raw_df: Any,
    coin_id: str,
    vs_currency: str,
) -> str:
    """Generate cache key for unnesting operations.

    Args:
        raw_df: Raw DataFrame to generate hash from
        coin_id: Cryptocurrency identifier
        vs_currency: Target currency

    Returns:
        Cache key string
    """
    data_hash = get_data_hash(raw_df)
    return f"unnest_{coin_id}_{vs_currency}_{data_hash}"


def get_data_hash(raw_df: Any) -> str:
    """Generate a hash for raw data to use in caching.

    Args:
        raw_df: Raw DataFrame or data structure

    Returns:
        Hash string
    """
    try:
        # Try to get a stable representation of the data
        if hasattr(raw_df, "to_dict"):
            data_repr = raw_df.to_dict()
        elif hasattr(raw_df, "to_list"):
            data_repr = raw_df.to_list()
        else:
            data_repr = str(raw_df)

        data_str = json.dumps(data_repr, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()
    except Exception:
        return "unknown"
