{{
  config(
    materialized='incremental',
    unique_key='date_day'
  )
}}

with daily_prices as (
    select
        timestamp,
        price,
        volume,
        -- Normalize timestamps to day for granular time-series partitioning
        date_trunc('day', timestamp)::date as date_day
    from {{ ref('stg_bitcoin_prices') }}

    {% if is_incremental() %}
        -- Watermark Strategy: Re-processes the latest date to ensure intra-day 
        -- records are captured until the day is finalized.
        where
            date_trunc('day', timestamp)
            >= (select max(date_day) from {{ this }})
    {% endif %}
),

final as (
    select
        date_day,
        -- Financial OHLC aggregation using DuckDB arg_min/arg_max
        arg_min(price, timestamp) as open_price,  -- Price at market open
        max(price) as high_price,                 -- Period high
        min(price) as low_price,                  -- Period low
        arg_max(price, timestamp) as close_price, -- Price at market close

        -- Volume and Data Quality signals
        sum(volume) as daily_volume,
        count(*) as samples_count,

        -- Intraday Volatility: (High - Low) / Low
        round(((max(price) - min(price)) / min(price)) * 100, 2)
            as volatility_pct

    from daily_prices
    group by 1
)

select * from final
