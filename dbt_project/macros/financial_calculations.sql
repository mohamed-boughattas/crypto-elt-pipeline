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
