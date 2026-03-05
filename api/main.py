"""FastAPI endpoint layer for serving Gold layer data.

This module provides a REST API for accessing cryptocurrency market data
from the DuckDB Gold layer. It demonstrates full-stack data engineering
skills by exposing the data warehouse via a modern API.

Features:
- RESTful endpoints for candlestick data
- Query parameters for filtering
- CORS support for web applications
- Error handling and logging
- OpenAPI documentation
- Rate limiting
- Request ID tracking
- Response caching
"""

import logging
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Annotated

import duckdb
import pendulum
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, ConfigDict, Field

from crypto_elt_pipeline.constants import DUCKDB_PATH

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "request_id": "%(request_id)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

# Configuration from environment
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))
API_RATE_PERIOD = int(os.getenv("API_RATE_PERIOD", "60"))


# Simple in-memory rate limiter
class RateLimiter:
    """Simple in-memory rate limiter for API requests."""

    def __init__(self, requests: int, period: int):
        """Initialize rate limiter.

        Args:
            requests: Maximum number of requests allowed
            period: Time period in seconds
        """
        self.requests = requests
        self.period = period
        self.clients: dict[str, list[datetime]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client.

        Args:
            client_id: Client identifier (IP address or API key)

        Returns:
            True if request is allowed, False otherwise
        """
        now = pendulum.now()

        if client_id not in self.clients:
            self.clients[client_id] = []

        # Remove old requests outside the time window
        self.clients[client_id] = [
            req_time
            for req_time in self.clients[client_id]
            if (pendulum.instance(now) - pendulum.instance(req_time)).total_seconds() < self.period
        ]

        if len(self.clients[client_id]) >= self.requests:
            return False

        self.clients[client_id].append(now)
        return True


# Initialize rate limiter with higher limits for testing
# In production, these would be lower, but for testing we need higher limits
TEST_RATE_LIMIT = int(os.getenv("TEST_RATE_LIMIT", str(API_RATE_LIMIT)))
TEST_RATE_PERIOD = int(os.getenv("TEST_RATE_PERIOD", str(API_RATE_PERIOD)))

rate_limiter = RateLimiter(requests=TEST_RATE_LIMIT, period=TEST_RATE_PERIOD)


# Database connection dependency
@contextmanager
def get_db_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get a read-only connection to DuckDB with automatic cleanup.

    Yields:
        DuckDB connection object

    Raises:
        HTTPException: If database connection fails
    """
    conn = None
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        yield conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed") from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")


# Request ID middleware
async def add_request_id(request, call_next):
    """Add unique request ID to each request for tracing."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Add request ID to logging context
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = getattr(request.state, "request_id", "")
        return record

    logging.setLogRecordFactory(record_factory)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    # Reset logging factory
    logging.setLogRecordFactory(old_factory)

    return response


# Initialize FastAPI app
app = FastAPI(
    title="Crypto ELT Pipeline API",
    description="REST API for cryptocurrency market data from the ELT pipeline",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.middleware("http")(add_request_id)


# Pydantic models for request/response
class CandlestickData(BaseModel):
    """Candlestick data model."""

    trade_date: date
    coin: str
    open_price: float = Field(..., gt=0)
    high_price: float = Field(..., gt=0)
    low_price: float = Field(..., gt=0)
    close_price: float = Field(..., gt=0)
    daily_volume: float = Field(..., ge=0)
    volatility_pct: float = Field(..., ge=0)
    samples_count: int = Field(..., gt=0)
    sma_7: float | None = None
    sma_25: float | None = None
    bb_middle: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    bb_position: float | None = None
    daily_change_pct: float | None = None
    price_range: float | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trade_date": "2026-03-01",
                "coin": "bitcoin",
                "open_price": 42500.0,
                "high_price": 43000.0,
                "low_price": 42000.0,
                "close_price": 42800.0,
                "daily_volume": 25000000000.0,
                "volatility_pct": 2.38,
                "samples_count": 24,
                "sma_7": 42650.0,
                "sma_25": 42400.0,
            }
        }
    )


class CoinListResponse(BaseModel):
    """Response model for coin list."""

    coins: list[str]
    count: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    database_path: str
    database_exists: bool
    database_size_mb: float | None = None
    last_updated: date | None = None
    timestamp: datetime


# Rate limiting dependency
async def check_rate_limit(request: Request, response: Response) -> None:
    """Check rate limit for client IP.

    Raises:
        HTTPException: If rate limit is exceeded
    """
    client_id = request.client.host if request.client else "unknown"

    if not rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for client: {client_id}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {API_RATE_LIMIT} requests per {API_RATE_PERIOD} seconds.",
        )

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(API_RATE_LIMIT)
    response.headers["X-RateLimit-Period"] = str(API_RATE_PERIOD)


# Cache headers helper
def add_cache_headers(response: Response, max_age: int = 60) -> None:
    """Add cache control headers to response.

    Args:
        response: FastAPI Response object
        max_age: Cache max age in seconds
    """
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["X-Cache-TTL"] = str(max_age)


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(response: Response):
    """Health check endpoint to verify API and database status."""
    try:
        db_exists = DUCKDB_PATH.exists()
        db_size_mb = None
        last_updated = None

        if db_exists:
            # Get database file size
            db_size_mb = DUCKDB_PATH.stat().st_size / (1024 * 1024)

            # Get last data update date
            with get_db_connection() as conn:
                result = conn.execute(
                    "SELECT MAX(trade_date) FROM mart.fct_crypto_candlesticks"
                ).fetchone()
                if result and result[0]:
                    last_updated = result[0]

        health_data = HealthResponse(
            status="healthy" if db_exists else "unhealthy",
            database_path=str(DUCKDB_PATH),
            database_exists=db_exists,
            database_size_mb=round(db_size_mb, 2) if db_size_mb else None,
            last_updated=last_updated,
            timestamp=pendulum.now(),
        )

        # Add cache headers (health check can be cached briefly)
        add_cache_headers(response, max_age=30)

        return health_data

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable") from e


# List available coins with pagination
@app.get("/api/v1/coins", response_model=CoinListResponse, tags=["Coins"])
async def list_coins(
    response: Response,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
):
    """Get list of available cryptocurrencies with pagination.

    Args:
        response: FastAPI Response object
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)

    Returns:
        Paginated list of coins
    """
    try:
        with get_db_connection() as conn:
            # Get total count
            count_result = conn.execute(
                "SELECT COUNT(DISTINCT coin) FROM mart.fct_crypto_candlesticks"
            ).fetchone()
            total_count = count_result[0] if count_result else 0

            # Get paginated results
            offset = (page - 1) * page_size
            query = """
                SELECT DISTINCT coin
                FROM mart.fct_crypto_candlesticks
                ORDER BY coin
                LIMIT ? OFFSET ?
            """
            results = conn.execute(query, [page_size, offset]).fetchall()

            coins = [row[0] for row in results]
            total_pages = (total_count + page_size - 1) // page_size

            # Add cache headers (coin list changes rarely)
            add_cache_headers(response, max_age=300)

            return CoinListResponse(
                coins=coins,
                count=len(coins),
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )

    except Exception as e:
        logger.error(f"Failed to list coins: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve coins") from e


# Get candlestick data for a specific coin
@app.get(
    "/api/v1/candlesticks/{coin}",
    response_model=list[CandlestickData],
    tags=["Candlesticks"],
    dependencies=[Depends(check_rate_limit)],
)
async def get_candlesticks(
    response: Response,
    coin: Annotated[
        str,
        Path(
            ...,
            pattern=r"^[a-z0-9-]+$",
            min_length=2,
            max_length=50,
            description="Cryptocurrency identifier (e.g., bitcoin, ethereum)",
        ),
    ],
    start_date: date | None = None,
    end_date: date | None = None,
    days: Annotated[int, Query(ge=1, le=365, description="Number of days to return")] = 30,
):
    """
    Get OHLC candlestick data for a specific cryptocurrency.

    - **coin**: Cryptocurrency identifier (e.g., bitcoin, ethereum)
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    - **days**: Number of days to return (default: 30, max: 365)

    Returns daily candlestick data with technical indicators.
    """
    try:
        with get_db_connection() as conn:
            # Build query with parameterized filters
            query = """
                SELECT
                    trade_date,
                    coin,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    daily_volume,
                    volatility_pct,
                    samples_count,
                    sma_7,
                    sma_25,
                    bb_middle,
                    bb_upper,
                    bb_lower,
                    bb_width,
                    bb_position,
                    daily_change_pct,
                    price_range
                FROM mart.fct_crypto_candlesticks
                WHERE coin = ?
            """
            params: list[object] = [coin]

            # Add date filters if provided
            if start_date:
                query += " AND trade_date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND trade_date <= ?"
                params.append(end_date)

            # Order and limit
            query += " ORDER BY trade_date DESC LIMIT ?"
            params.append(days)

            results = conn.execute(query, params).fetchall()

            if not results:
                raise HTTPException(status_code=404, detail=f"No data found for coin: {coin}")

            # Convert to response models
            candlesticks = [
                CandlestickData(
                    trade_date=row[0],
                    coin=row[1],
                    open_price=row[2],
                    high_price=row[3],
                    low_price=row[4],
                    close_price=row[5],
                    daily_volume=row[6],
                    volatility_pct=row[7],
                    samples_count=row[8],
                    sma_7=row[9],
                    sma_25=row[10],
                    bb_middle=row[11],
                    bb_upper=row[12],
                    bb_lower=row[13],
                    bb_width=row[14],
                    bb_position=row[15],
                    daily_change_pct=row[16],
                    price_range=row[17],
                )
                for row in results
            ]

            # Add cache headers (historical data can be cached)
            add_cache_headers(response, max_age=60)

            return candlesticks

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get candlesticks for {coin}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve candlestick data") from e


# Get latest data for all coins
@app.get(
    "/api/v1/latest",
    response_model=list[CandlestickData],
    tags=["Candlesticks"],
    dependencies=[Depends(check_rate_limit)],
)
async def get_latest_data(response: Response):
    """Get the latest candlestick data for all cryptocurrencies."""
    try:
        with get_db_connection() as conn:
            query = """
                WITH ranked AS (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (PARTITION BY coin ORDER BY trade_date DESC) as rn
                    FROM mart.fct_crypto_candlesticks
                )
                SELECT
                    trade_date,
                    coin,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    daily_volume,
                    volatility_pct,
                    samples_count,
                    sma_7,
                    sma_25,
                    bb_middle,
                    bb_upper,
                    bb_lower,
                    bb_width,
                    bb_position,
                    daily_change_pct,
                    price_range
                FROM ranked
                WHERE rn = 1
                ORDER BY coin
            """

            results = conn.execute(query).fetchall()

            candlesticks = [
                CandlestickData(
                    trade_date=row[0],
                    coin=row[1],
                    open_price=row[2],
                    high_price=row[3],
                    low_price=row[4],
                    close_price=row[5],
                    daily_volume=row[6],
                    volatility_pct=row[7],
                    samples_count=row[8],
                    sma_7=row[9],
                    sma_25=row[10],
                    bb_middle=row[11],
                    bb_upper=row[12],
                    bb_lower=row[13],
                    bb_width=row[14],
                    bb_position=row[15],
                    daily_change_pct=row[16],
                    price_range=row[17],
                )
                for row in results
            ]

            # Add cache headers (latest data changes frequently)
            add_cache_headers(response, max_age=30)

            return candlesticks

    except Exception as e:
        logger.error(f"Failed to get latest data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve latest data") from e


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Crypto ELT Pipeline API",
        "version": "1.1.0",
        "description": "REST API for cryptocurrency market data",
        "documentation": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
