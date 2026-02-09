{{
  config(
    materialized='incremental',
    unique_key='timestamp',
    on_schema_change='sync_all_columns'
  )
}}

with raw_data as (
    -- Reference the source defined in your _sources.yml
    select * from {{ source('coingecko', 'bitcoin_prices') }}

    {% if is_incremental() %}
        -- Performance optimization: only pull data since the last run
        -- This ensures scalability as your DuckDB file grows
        where timestamp > (select max(timestamp) from {{ this }})
    {% endif %}
),

renamed as (
    select
        coin,
        currency,
        timestamp,
        price,
        market_cap,
        volume
    from raw_data
)

select * from renamed
