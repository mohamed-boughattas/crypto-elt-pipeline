"""Pydantic response models."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CandlestickData(BaseModel):
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
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

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
    coins: list[str]
    count: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    database_path: str
    database_exists: bool
    database_size_mb: float | None = None
    last_updated: date | None = None
    timestamp: datetime
