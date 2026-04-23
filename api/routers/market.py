"""Market data endpoints."""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from api.db import get_db_connection
from api.models import CandlestickData, CoinListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Market"])


@router.get("/coins", response_model=CoinListResponse)
async def list_coins(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
) -> CoinListResponse:
    """List available cryptocurrencies with pagination."""
    try:
        with get_db_connection() as conn:
            count_result = conn.execute(
                "SELECT COUNT(DISTINCT coin) FROM mart.fct_crypto_candlesticks"
            ).fetchone()
            total_count = count_result[0] if count_result else 0

            offset = (page - 1) * page_size
            results = conn.execute(
                "SELECT DISTINCT coin FROM mart.fct_crypto_candlesticks ORDER BY coin LIMIT ? OFFSET ?",
                [page_size, offset],
            ).fetchall()

            coins = [row[0] for row in results]
            total_pages = (total_count + page_size - 1) // page_size

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


@router.get("/candlesticks/{coin}", response_model=list[CandlestickData])
async def get_candlesticks(
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
) -> list[CandlestickData]:
    """Get OHLC candlestick data for a specific cryptocurrency."""
    try:
        with get_db_connection() as conn:
            query = """
                SELECT
                    trade_date, coin, open_price, high_price, low_price, close_price,
                    daily_volume, volatility_pct, samples_count, sma_7, sma_25,
                    bb_middle, bb_upper, bb_lower, bb_width, bb_position,
                    daily_change_pct, price_range, rsi, macd, macd_signal, macd_histogram
                FROM mart.fct_crypto_candlesticks
                WHERE coin = ?
            """
            params: list[object] = [coin]

            if start_date:
                query += " AND trade_date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND trade_date <= ?"
                params.append(end_date)

            query += " ORDER BY trade_date DESC LIMIT ?"
            params.append(days)

            cursor = conn.execute(query, params)
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()

            if not rows:
                raise HTTPException(status_code=404, detail=f"No data found for coin: {coin}")

            return [CandlestickData(**dict(zip(columns, row, strict=False))) for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get candlesticks for {coin}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve candlestick data") from e


@router.get("/latest", response_model=list[CandlestickData])
async def get_latest_data() -> list[CandlestickData]:
    """Get the latest candlestick data for all cryptocurrencies."""
    try:
        with get_db_connection() as conn:
            query = """
                WITH ranked AS (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY coin ORDER BY trade_date DESC) as rn
                    FROM mart.fct_crypto_candlesticks
                )
                SELECT
                    trade_date, coin, open_price, high_price, low_price, close_price,
                    daily_volume, volatility_pct, samples_count, sma_7, sma_25,
                    bb_middle, bb_upper, bb_lower, bb_width, bb_position,
                    daily_change_pct, price_range, rsi, macd, macd_signal, macd_histogram
                FROM ranked
                WHERE rn = 1
                ORDER BY coin
            """
            cursor = conn.execute(query)
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()

            return [CandlestickData(**dict(zip(columns, row, strict=False))) for row in rows]

    except Exception as e:
        logger.error(f"Failed to get latest data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve latest data") from e
