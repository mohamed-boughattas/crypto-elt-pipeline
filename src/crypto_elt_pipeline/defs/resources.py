import dagster as dg
from dagster_dbt import DbtCliResource
from dagster_duckdb_polars import DuckDBPolarsIOManager

from crypto_elt_pipeline.constants import DUCKDB_PATH
from crypto_elt_pipeline.defs.assets.dbt import dbt_project

# 1. IO Manager
# Configures DuckDB as the storage engine and Polars for efficient data loading.
database_io_manager = DuckDBPolarsIOManager(
    database=str(DUCKDB_PATH),
)

# 2. dbt Resource
# Configures the dbt CLI environment.
project_dir_str = str(dbt_project.project_dir)

dbt_resource = DbtCliResource(
    project_dir=project_dir_str,
    profiles_dir=project_dir_str,
)


@dg.definitions
def resources() -> dg.Definitions:
    return dg.Definitions(
        resources={
            "io_manager": database_io_manager,
            "dbt": dbt_resource,
        },
    )
