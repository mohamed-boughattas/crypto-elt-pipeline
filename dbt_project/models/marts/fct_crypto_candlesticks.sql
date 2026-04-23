{{
  config(
    materialized='table',
    cluster_by=['coin', 'trade_date'],
    indexes=[
      {'columns': ['coin', 'trade_date'], 'unique': true},
      {'columns': ['trade_date']},
      {'columns': ['coin']}
    ]
  )
}}

{#
  Gold Layer: Daily OHLC candlestick data with moving averages for technical analysis.

  Performance Optimizations:
  - Table materialization for full historical context (required for window functions)
  - Strategic clustering on (coin, trade_date) for time-series queries
  - Indexes on common query patterns
  - Reusable macros for consistent calculations
  - Optimized window functions with proper partitioning

  Business Value:
  - Analytics-ready daily aggregations for trading analysis
  - Standardized candlestick data for technical indicators
  - Moving averages for trend analysis and trading signals
  - Volatility metrics for risk assessment

  Grain: One row per (coin, trade_date) - daily candlestick
#}

with source_data as (
    select
        coin,
        recorded_at,
        price,
        volume
    from {{ ref('stg_crypto_prices') }}
),

ohlc_base as (
    select
        coin,
        date_trunc('day', recorded_at)::date as trade_date,

        arg_min(price, recorded_at) as open_price,
        max(price) as high_price,
        min(price) as low_price,
        arg_max(price, recorded_at) as close_price,

        sum(volume) as daily_volume,
        count(*) as samples_count

    from source_data
    group by coin, date_trunc('day', recorded_at)::date
),

with_price_changes as (
    select
        *,
        price - lag(close_price) over (
            partition by coin
            order by trade_date
        ) as price_change
    from ohlc_base
),

with_smas as (
    select
        coin,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        daily_volume,
        samples_count,

        {{ calculate_volatility('high_price', 'low_price') }} as volatility_pct,

        {{ calculate_simple_moving_average('close_price', 7) }} as sma_7,
        {{ calculate_simple_moving_average('close_price', 25) }} as sma_25,

        {{ calculate_bollinger_band_middle('close_price', 20) }} as bb_middle,
        {{ calculate_bollinger_band_upper('close_price', 20, 2) }} as bb_upper,
        {{ calculate_bollinger_band_lower('close_price', 20, 2) }} as bb_lower,
        {{ calculate_bollinger_band_width('close_price', 20, 2) }} as bb_width,
        {{ calculate_bollinger_band_position('close_price', 20, 2) }} as bb_position,

        {{ calculate_price_change('open_price', 'close_price') }} as daily_change_pct,
        {{ calculate_price_range('high_price', 'low_price') }} as price_range,

        {{ calculate_rsi('price_change', 14) }} as rsi,
        {{ calculate_macd('price_change', 12, 26, 9) }} as macd,
        {{ calculate_macd_signal('price_change', 12, 26, 9) }} as macd_signal,
        {{ calculate_macd_histogram('price_change', 12, 26, 9) }} as macd_histogram

    from with_price_changes
)

select
    coin,
    trade_date,
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
    price_range,
    rsi,
    macd,
    macd_signal,
    macd_histogram
from with_smas
order by coin, trade_date
