-- Macro to get list of coins from seed file
-- This provides a single source of truth for coin IDs across dbt tests

{% macro get_coin_list() %}
    {{ return(adapter.dispatch('get_coin_list', 'dbt_utils')()) }}
{% endmacro %}

{% macro default__get_coin_list() %}
    {% set coin_query %}
        SELECT coin_id
        FROM {{ ref('coins_config') }}
        ORDER BY coin_id
    {% endset %}
    
    {% set results = run_query(coin_query) %}
    {% set coin_ids = [] %}
    
    {% for row in results %}
        {% do coin_ids.append(row[0]) %}
    {% endfor %}
    
    {{ return(coin_ids) }}
{% endmacro %}
