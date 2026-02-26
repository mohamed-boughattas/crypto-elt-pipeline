-- Test that Bollinger Bands follow logical consistency (Upper >= Middle >= Lower)
-- Singular test: Returns failing rows
-- Note: Excludes NULL values (first 19 rows due to 20-day window)
select
    coin,
    trade_date,
    bb_upper,
    bb_middle,
    bb_lower
from {{ ref('fct_crypto_candlesticks') }}
where
    bb_upper is not null
    and bb_middle is not null
    and bb_lower is not null
    and (
        bb_upper < bb_middle
        or bb_middle < bb_lower
    )
