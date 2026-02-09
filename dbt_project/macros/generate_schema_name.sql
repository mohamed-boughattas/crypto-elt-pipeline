{% macro generate_schema_name(custom_schema_name, node) -%}
    {# Overrides dbt default to prevent schema concatenation (e.g., 'main_staging' becomes 'staging') #}
    {%- set default_schema = target.schema -%}
    
    {# Resolves to the explicit custom schema if defined, otherwise falls back to target default #}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
