{{
  config(
    materialized='incremental',
    unique_key='recorded_at',
    on_schema_change='sync_all_columns'
  )
}}

with source as (
    -- 1. Reference the raw landing zone
    select
        coin,
        currency,
        timestamp as recorded_at,
        price,
        market_cap,
        volume
    from {{ source('coingecko', 'bitcoin_prices') }}
),

{% if is_incremental() %}
-- 2. Calculate the threshold separately
    latest_threshold as (
        select max(recorded_at) - interval '1 hour' as limit_time
        from {{ this }}
    ),
{% endif %}

final as (
    select
        s.coin,
        s.currency,
        s.recorded_at,
        s.price,
        s.market_cap,
        s.volume
    from source as s

    {% if is_incremental() %}
    -- 3. Cross join to use the calculated constant for filtering
        cross join latest_threshold
        where s.recorded_at >= latest_threshold.limit_time
    {% endif %}
)

select * from final
