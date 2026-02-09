{{
  config(
    materialized='incremental',
    unique_key='timestamp',
    on_schema_change='sync_all_columns'
  )
}}

with raw_data as (
    -- 1. Bronze-to-Silver Ingestion
    -- References the raw landing zone managed by PyAirbyte/Dagster.
    select * from {{ source('coingecko', 'bitcoin_prices') }}

    {% if is_incremental() %}
        -- 2. Performance Optimization & Late Data Handling
        -- Filters for new records using a 1-hour lookback window to ensure 
        -- zero data loss during intra-hour refreshes.
        where
            timestamp
            >= (select max(timestamp) - interval '1 hour' from {{ this }})
    {% endif %}
),

final as (
    select
        -- 3. Schema Enforcement (Silver Layer)
        -- Normalizes data types to ensure consistent analytical downstream performance.
        coin::varchar as coin,
        currency::varchar as currency,
        timestamp::timestamp as timestamp,
        price::double as price,
        market_cap::double as market_cap,
        volume::double as volume
    from raw_data
)

select * from final
