-- Test for uniqueness of coin and recorded_at combination
-- Singular test: Returns failing rows (duplicates)
select
    coin,
    recorded_at,
    count(*) as duplicate_count
from {{ ref('stg_crypto_prices') }}
group by coin, recorded_at
having count(*) > 1
