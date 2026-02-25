{#
  Custom schema name generator for DuckDB.

  This macro overrides dbt's default behavior to provide clean schema names
  without concatenation. By default, dbt would create schemas like 'main_staging'
  when a custom schema is specified. This macro returns just the custom schema name.

  Args:
    custom_schema_name: The custom schema defined in model config (e.g., 'staging', 'mart')
    node: The dbt node object (unused but required by dbt interface)

  Returns:
    The schema name to use for the model:
    - If custom_schema_name is defined: returns the custom schema name (e.g., 'staging')
    - If custom_schema_name is none: returns the target schema (e.g., 'main')

  Example:
    Model with `{{ config(schema='staging') }}` → schema: 'staging'
    Model without custom schema → schema: 'main' (from target)

  This enables the Medallion Architecture pattern:
    - raw (Bronze): Raw data from ingestion
    - staging (Silver): Cleaned and transformed data
    - mart (Gold): Business-ready aggregations
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
