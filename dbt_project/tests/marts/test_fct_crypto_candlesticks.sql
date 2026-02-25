-- Test that OHLC values follow logical consistency (High >= Low, Open/Close between High/Low)
-- Singular test: Returns failing rows
select
    coin,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price
from {{ ref('fct_crypto_candlesticks') }}
where
    high_price < low_price
    or open_price < low_price
    or open_price > high_price
    or close_price < low_price
    or close_price > high_price
