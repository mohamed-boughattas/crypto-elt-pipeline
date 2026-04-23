"""Health and root endpoints."""

import logging
from datetime import date

import pendulum
from fastapi import APIRouter, HTTPException

from api.db import get_db_connection
from api.models import HealthResponse
from crypto_elt_pipeline.constants import DUCKDB_PATH

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Verify API and database status."""
    try:
        db_exists = DUCKDB_PATH.exists()
        db_size_mb = None
        last_updated: date | None = None

        if db_exists:
            db_size_mb = DUCKDB_PATH.stat().st_size / (1024 * 1024)
            with get_db_connection() as conn:
                result = conn.execute(
                    "SELECT MAX(trade_date) FROM mart.fct_crypto_candlesticks"
                ).fetchone()
                if result and result[0]:
                    last_updated = result[0]

        return HealthResponse(
            status="healthy" if db_exists else "unhealthy",
            database_path=str(DUCKDB_PATH),
            database_exists=db_exists,
            database_size_mb=round(db_size_mb, 2) if db_size_mb else None,
            last_updated=last_updated,
            timestamp=pendulum.now(),
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable") from e


@router.get("/")
async def root() -> dict[str, str]:
    """API information."""
    return {
        "name": "Crypto ELT Pipeline API",
        "version": "1.1.0",
        "description": "REST API for cryptocurrency market data",
        "documentation": "/docs",
        "health": "/health",
    }
