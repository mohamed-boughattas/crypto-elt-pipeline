{{
  config(
    materialized='incremental',
    unique_key='timestamp',
    on_schema_change='sync_all_columns'
  )
}}

with raw_data as (
    -- 1. Source Reference
    select * from {{ source('coingecko', 'bitcoin_prices') }}

    {% if is_incremental() %}
        -- 2. Incremental Logic with "Safety Net"
        where
            timestamp
            >= (select max(timestamp) - interval '1 hour' from {{ this }})
    {% endif %}
),

final as (
    select
        -- 3. Explicit Casting for Robustness
        coin::varchar as coin,
        currency::varchar as currency,
        timestamp::timestamp as timestamp,
        price::double as price,
        market_cap::double as market_cap,
        volume::double as volume
    from raw_data
)

select * from final
