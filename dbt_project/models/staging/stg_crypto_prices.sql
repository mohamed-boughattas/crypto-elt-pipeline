{{
  config(
    materialized='incremental',
    unique_key=['coin', 'recorded_at'],
    on_schema_change='sync_all_columns',
    cluster_by=['coin', 'recorded_at']
  )
}}

-- Silver Layer: Clean and type-enforce the raw flattened market data
-- The raw layer now provides pre-flattened time-series data
-- This model handles deduplication and data quality filtering

with raw_data as (
    -- Reference the raw landing zone (Bronze) - now with flattened data
    select
        coin,
        currency,
        ingested_at,
        recorded_at,
        price,
        market_cap,
        volume
    from {{ source('coingecko', 'crypto_prices') }}
),

-- Filter out invalid records
filtered as (
    select
        coin,
        currency,
        ingested_at,
        recorded_at,
        -- Round prices to 8 decimal places for consistency
        round(price, 8) as price,
        round(market_cap, 2) as market_cap,
        round(volume, 2) as volume
    from raw_data
    where
        price > 0
        and recorded_at is not null
        and market_cap >= 0
        and volume >= 0
),

{% if is_incremental() %}
-- Calculate watermark per coin for incremental processing
-- Subtract 1 hour buffer for late-arriving data
    latest_thresholds as (
        select
            coin,
            max(recorded_at) - interval '1 hour' as limit_time
        from {{ this }}
        group by coin
    ),
{% endif %}

-- Filter to only new/updated records
new_records as (
    select
        f.coin,
        f.currency,
        f.ingested_at,
        f.recorded_at,
        f.price,
        f.market_cap,
        f.volume
    from filtered as f

    {% if is_incremental() %}
    -- Left join handles both new and existing coins:
    --    - New coins: lt.limit_time IS NULL (no existing data)
    --    - Existing coins: filter to only new records
        left join latest_thresholds as lt on f.coin = lt.coin
        where
            lt.limit_time is null
            or f.recorded_at >= lt.limit_time
    {% endif %}
),

-- Deduplicate and sort for time-series integrity
-- Use ORDER BY with ingested_at DESC to keep the most recently ingested record
-- when duplicate (coin, recorded_at) pairs exist (deterministic selection)
deduped as (
    select distinct on (coin, recorded_at)
        coin,
        currency,
        ingested_at,
        recorded_at,
        price,
        market_cap,
        volume
    from new_records
    order by coin asc, recorded_at asc, ingested_at desc
)

-- Explicit column list for contract clarity
select
    coin,
    currency,
    ingested_at,
    recorded_at,
    price,
    market_cap,
    volume
from deduped
