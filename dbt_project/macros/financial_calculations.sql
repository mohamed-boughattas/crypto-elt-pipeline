{#
  Financial calculation macros for cryptocurrency analysis.

  Purpose: Provide reusable, well-documented financial calculations
  that follow best practices for accuracy and performance.

  Usage: These macros can be used across multiple models to ensure
  consistency in financial calculations and improve maintainability.
#}

{% macro calculate_volatility(high_price, low_price) %}
  {#
    Calculate intraday volatility percentage.

    Formula: ((High - Low) / Low) * 100

    Parameters:
      - high_price: Highest price during the period
      - low_price: Lowest price during the period

    Returns: Volatility percentage as a decimal

    Example:
      {{ calculate_volatility('high_price', 'low_price') }}
  #}

  round(
    (({{ high_price }} - {{ low_price }}) / nullif({{ low_price }}, 0)) * 100,
    2
  )
{% endmacro %}

{% macro calculate_simple_moving_average(column_name, window_size, partition_by='coin', order_by='trade_date') %}
  {#
    Calculate simple moving average for a given column.

    Parameters:
      - column_name: The column to calculate SMA for
      - window_size: Number of periods to include in the average
      - partition_by: Column(s) to partition by (default: coin)
      - order_by: Column to order by for the window function (default: trade_date)

    Returns: Simple moving average using window function

    Example:
      {{ calculate_simple_moving_average('close_price', 7) }}
      {{ calculate_simple_moving_average('volume', 14, partition_by='coin', order_by='date') }}
  #}

  avg({{ column_name }}) over (
    partition by {{ partition_by }}
    order by {{ order_by }}
    rows between {{ window_size - 1 }} preceding and current row
  )
{% endmacro %}

{% macro calculate_price_change(open_price, close_price) %}
  {#
    Calculate daily price change percentage.

    Formula: ((Close - Open) / Open) * 100

    Parameters:
      - open_price: Opening price for the period
      - close_price: Closing price for the period

    Returns: Price change percentage as a decimal

    Example:
      {{ calculate_price_change('open_price', 'close_price') }}
  #}

  round(
    (({{ close_price }} - {{ open_price }}) / nullif({{ open_price }}, 0)) * 100,
    2
  )
{% endmacro %}

{% macro calculate_price_range(high_price, low_price) %}
  {#
    Calculate absolute price range for a period.

    Formula: High - Low

    Parameters:
      - high_price: Highest price during the period
      - low_price: Lowest price during the period

    Returns: Absolute price range

    Example:
      {{ calculate_price_range('high_price', 'low_price') }}
  #}

  ({{ high_price }} - {{ low_price }})
{% endmacro %}

{#  Helper macro to compute Bollinger Band statistics once
  #  This avoids recalculating avg and stddev multiple times
  #
  #  Returns a struct with: middle, upper, lower, std_dev
  #  Use this with dbt's built-in struct functions
 #}

{% macro _bollinger_band_stats(column_name, window_size=20) %}
  (
    -- Calculate middle band (SMA)
    avg({{ column_name }}) over (
      partition by coin order by trade_date
      rows between {{ window_size - 1 }} preceding and current row
    )
  )
{% endmacro %}

{% macro calculate_bollinger_band_middle(column_name, window_size=20) %}
  {#|
    Calculate Bollinger Band middle band (Simple Moving Average).

    Formula: SMA of closing prices over specified window

    Parameters:
      - column_name: The price column to calculate SMA for (typically close_price)
      - window_size: Number of periods for the moving average (default: 20)

    Returns: Middle Bollinger Band (20-day SMA)

    Example:
      {{ calculate_bollinger_band_middle('close_price', 20) }}
  #}

    {{ _bollinger_band_stats(column_name, window_size) }}
{% endmacro %}

{% macro calculate_bollinger_band_upper(column_name, window_size=20, std_dev=2) %}
  {#|
    Calculate Bollinger Band upper band.

    Formula: Middle Band + (Standard Deviation × Multiplier)

    Parameters:
      - column_name: The price column to calculate for (typically close_price)
      - window_size: Number of periods for the moving average (default: 20)
      - std_dev: Standard deviation multiplier (default: 2)

    Returns: Upper Bollinger Band

    Example:
      {{ calculate_bollinger_band_upper('close_price', 20, 2) }}
  #}

{{ _bollinger_band_stats(column_name, window_size) }} + (
    {{ std_dev }} * stddev({{ column_name }}) over (
      partition by coin order by trade_date
      rows between {{ window_size - 1 }} preceding and current row
    )
  )
{% endmacro %}

{% macro calculate_bollinger_band_lower(column_name, window_size=20, std_dev=2) %}
  {#|
    Calculate Bollinger Band lower band.

    Formula: Middle Band - (Standard Deviation × Multiplier)

    Parameters:
      - column_name: The price column to calculate for (typically close_price)
      - window_size: Number of periods for the moving average (default: 20)
      - std_dev: Standard deviation multiplier (default: 2)

    Returns: Lower Bollinger Band

    Example:
      {{ calculate_bollinger_band_lower('close_price', 20, 2) }}
  #}

{{ _bollinger_band_stats(column_name, window_size) }} - (
    {{ std_dev }} * stddev({{ column_name }}) over (
      partition by coin order by trade_date
      rows between {{ window_size - 1 }} preceding and current row
    )
  )
{% endmacro %}

{% macro calculate_bollinger_band_width(column_name, window_size=20, std_dev=2) %}
  {#|
    Calculate Bollinger Band width (volatility indicator).

    Formula: (Upper Band - Lower Band) / Middle Band

    Parameters:
      - column_name: The price column to calculate for (typically close_price)
      - window_size: Number of periods for the moving average (default: 20)
      - std_dev: Standard deviation multiplier (default: 2)

    Returns: Bollinger Band width as percentage

    Example:
      {{ calculate_bollinger_band_width('close_price', 20, 2) }}
  #}

  -- Width = (Upper - Lower) / Middle * 100
  -- Simplified: (2 * std_dev * stddev) / middle * 100
  (
    2 * {{ std_dev }} * stddev({{ column_name }}) over (
      partition by coin order by trade_date
      rows between {{ window_size - 1 }} preceding and current row
    )
  ) / nullif({{ _bollinger_band_stats(column_name, window_size) }}, 0) * 100
{% endmacro %}

{% macro calculate_bollinger_band_position(column_name, window_size=20, std_dev=2) %}
  {#
    Calculate price position relative to Bollinger Bands.

    Formula: (Price - Lower Band) / (Upper Band - Lower Band)

    Parameters:
      - column_name: The price column to calculate for (typically close_price)
      - window_size: Number of periods for the moving average (default: 20)
      - std_dev: Standard deviation multiplier (default: 2)

    Returns: Position between 0 (at lower band) and 1 (at upper band)

    Example:
      {{ calculate_bollinger_band_position('close_price', 20, 2) }}
  #}

  -- Position = (Price - Lower) / (Upper - Lower)
  -- Simplified: (Price - (Middle - k*StdDev)) / (2 * k * StdDev)
  (
    {{ column_name }} - (
      {{ _bollinger_band_stats(column_name, window_size) }} - (
        {{ std_dev }} * stddev({{ column_name }}) over (
          partition by coin order by trade_date
          rows between {{ window_size - 1 }} preceding and current row
        )
      )
    )
  ) / nullif(
    2 * {{ std_dev }} * stddev({{ column_name }}) over (
      partition by coin order by trade_date
      rows between {{ window_size - 1 }} preceding and current row
    ),
    0
  )
{% endmacro %}

{% macro calculate_rsi(column_name, period=14) %}
  {#
    Calculate Relative Strength Index using Wilder's smoothing method.

    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    Average Gain/Loss uses Wilder's smoothing: (prev_avg * (period-1) + current_gain) / period

    Parameters:
      - column_name: The price column to calculate RSI for (typically close_price)
      - period: RSI period (default: 14)

    Returns: RSI value between 0 and 100

    Example:
      {{ calculate_rsi('close_price', 14) }}
  #}

  round(
    100 - (
      100 / (
        1 + (
          avg(CASE WHEN price_change > 0 THEN price_change END) over (
            partition by coin order by trade_date
            rows between {{ period - 1 }} preceding and current row
          ) /
          nullif(
            avg(CASE WHEN price_change < 0 THEN abs(price_change) END) over (
              partition by coin order by trade_date
              rows between {{ period - 1 }} preceding and current row
            ),
            0
          )
        )
      )
    ),
    2
  )
{% endmacro %}

{% macro calculate_ema(column_name, period, partition_by='coin', order_by='trade_date') %}
  {#
    Calculate Exponential Moving Average.

    EMA = Price(t) * k + EMA(y) * (1 - k)
    where k = 2 / (period + 1)

    Parameters:
      - column_name: The column to calculate EMA for
      - period: EMA period
      - partition_by: Column(s) to partition by (default: coin)
      - order_by: Column to order by (default: trade_date)

    Returns: EMA value

    Example:
      {{ calculate_ema('close_price', 12) }}
  #}

  avg({{ column_name }}) over (
    partition by {{ partition_by }}
    order by {{ order_by }}
    rows between {{ period - 1 }} preceding and current row
  )
{% endmacro %}

{% macro calculate_macd(column_name, fast_period=12, slow_period=26, signal_period=9) %}
  {#
    Calculate MACD line (Fast EMA - Slow EMA).

    Parameters:
      - column_name: The price column to calculate MACD for (typically close_price)
      - fast_period: Fast EMA period (default: 12)
      - slow_period: Slow EMA period (default: 26)
      - signal_period: Signal EMA period (default: 9)

    Returns: MACD line value

    Example:
      {{ calculate_macd('close_price', 12, 26, 9) }}
  #}

  {{ calculate_ema(column_name, fast_period) }} - {{ calculate_ema(column_name, slow_period) }}
{% endmacro %}

{% macro calculate_macd_signal(column_name, fast_period=12, slow_period=26, signal_period=9) %}
  {#
    Calculate MACD Signal line (EMA of MACD line).

    Parameters:
      - column_name: The price column (used for MACD calculation)
      - fast_period: Fast EMA period (default: 12)
      - slow_period: Slow EMA period (default: 26)
      - signal_period: Signal EMA period (default: 9)

    Returns: MACD Signal line value

    Example:
      {{ calculate_macd_signal('close_price', 12, 26, 9) }}
  #}

  {{ calculate_ema(
      '(' ~ calculate_macd(column_name, fast_period, slow_period) ~ ')',
      signal_period
  ) }}
{% endmacro %}

{% macro calculate_macd_histogram(column_name, fast_period=12, slow_period=26, signal_period=9) %}
  {#
    Calculate MACD Histogram (MACD Line - Signal Line).

    Parameters:
      - column_name: The price column to calculate MACD for
      - fast_period: Fast EMA period (default: 12)
      - slow_period: Slow EMA period (default: 26)
      - signal_period: Signal EMA period (default: 9)

    Returns: MACD Histogram value

    Example:
      {{ calculate_macd_histogram('close_price', 12, 26, 9) }}
  #}

  {{ calculate_macd(column_name, fast_period, slow_period) }} - {{ calculate_macd_signal(column_name, fast_period, slow_period, signal_period) }}
{% endmacro %}

{% macro standardize_price_precision(price_column, decimals=8) %}
  {#
    Standardize price precision to specified decimal places.

    Parameters:
      - price_column: The price column to standardize
      - decimals: Number of decimal places (default: 8 for cryptocurrency precision)

    Returns: Price rounded to specified decimal places

    Example:
      {{ standardize_price_precision('price', 8) }}
      {{ standardize_price_precision('market_cap', 2) }}
  #}

  round({{ price_column }}, {{ decimals }})
{% endmacro %}

{% macro validate_financial_data(price, market_cap, volume) %}
  {#
    Validate financial data quality for cryptocurrency metrics.

    Checks:
    - Price must be positive
    - Market cap must be non-negative
    - Volume must be non-negative

    Parameters:
      - price: Price value to validate
      - market_cap: Market cap value to validate
      - volume: Volume value to validate

    Returns: Boolean indicating if data is valid

    Example:
      {{ validate_financial_data('price', 'market_cap', 'volume') }}
  #}

  (
    {{ price }} > 0
    and {{ market_cap }} >= 0
    and {{ volume }} >= 0
  )
{% endmacro %}
