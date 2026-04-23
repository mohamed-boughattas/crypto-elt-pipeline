"""Database connection dependency."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

import duckdb

from crypto_elt_pipeline.constants import DUCKDB_PATH

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Read-only DuckDB connection with automatic cleanup."""
    conn = None
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        yield conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as exc:
                logger.warning(f"Error closing database connection: {exc}")
