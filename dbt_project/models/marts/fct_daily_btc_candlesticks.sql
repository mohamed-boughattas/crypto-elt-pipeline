{{
  config(
    materialized='incremental',
    unique_key='date_day'
  )
}}

with daily_prices as (
    select
        -- Truncate timestamp to day for aggregation
        timestamp,
        price,
        date_trunc('day', timestamp) as date_day
    from {{ ref('stg_bitcoin_prices') }}

    {% if is_incremental() %}
        -- Incremental logic: Refresh the current day and add new ones
        -- This handles cases where more data arrives for the current 'today'
        where
            date_trunc('day', timestamp)
            >= (select max(date_day) from {{ this }})
    {% endif %}
),

final as (
    select
        date_day,
        -- Opening price: The price at the earliest timestamp of the day
        arg_min(price, timestamp) as open_price,
        -- Closing price: The price at the latest timestamp of the day
        arg_max(price, timestamp) as close_price,
        -- High/Low: Simple aggregates across the day
        max(price) as high_price,
        min(price) as low_price,
        -- Data quality metric: count data points per day
        count(*) as samples_count
    from daily_prices
    group by 1
)

select * from final
