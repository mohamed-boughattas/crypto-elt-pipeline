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
        -- Truncate to day and cast to DATE for a clean primary key
        date_trunc('day', timestamp)::date as date_day
    from {{ ref('stg_bitcoin_prices') }}

    {% if is_incremental() %}
        -- Smart Refresh: Always re-process the current day to capture new intra-day data.
        where
            date_trunc('day', timestamp)
            >= (select max(date_day) from {{ this }})
    {% endif %}
),

final as (
    select
        date_day,
        -- OHLC Logic: standard for financial time-series
        -- Price at first timestamp of the day
        arg_min(price, timestamp) as open_price,
        max(price) as high_price,                -- Highest price of the day
        min(price) as low_price,                 -- Lowest price of the day
        -- Price at last timestamp of the day
        arg_max(price, timestamp) as close_price,
        -- Volume & Quality Metrics
        sum(volume) as daily_volume,
        count(*) as samples_count,
        -- Optional: Daily Volatility calculation ((High - Low) / Low)
        round(((max(price) - min(price)) / min(price)) * 100, 2)
            as volatility_pct

    from daily_prices
    group by 1
)

select * from final
