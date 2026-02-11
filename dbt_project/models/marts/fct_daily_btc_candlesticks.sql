{{
  config(
    materialized='incremental',
    unique_key='trade_date',
    on_schema_change='sync_all_columns'
  )
}}

with source_data as (
    select
        recorded_at,
        price,
        volume,
        date_trunc('day', recorded_at)::date as trade_date
    from {{ ref('stg_bitcoin_prices') }}
),

{% if is_incremental() %}
-- Calculate the watermark in a separate CTE
    latest_watermark as (
        select max(trade_date) as last_date from {{ this }}
    ),
{% endif %}

filtered_prices as (
    select src.* from source_data as src
    {% if is_incremental() %}
        cross join latest_watermark
        where src.trade_date >= latest_watermark.last_date
    {% endif %}
),

final as (
    select
        trade_date,
        -- Financial OHLC aggregation using DuckDB arg_min/arg_max
        arg_min(price, recorded_at) as open_price,
        max(price) as high_price,
        min(price) as low_price,
        arg_max(price, recorded_at) as close_price,

        -- Volume and Data Quality signals
        sum(volume) as daily_volume,
        count(*) as samples_count,

        -- Intraday Volatility: (High - Low) / Low
        round(((max(price) - min(price)) / nullif(min(price), 0)) * 100, 2)
            as volatility_pct

    from filtered_prices
    group by 1
)

select * from final
