from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import (
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    DbtProject,
    dbt_assets,
)

# 1. Initialize the Project Object
DBT_PROJECT_DIR = Path(__file__).parents[4] / "dbt_project"
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()


# 2. Translator for UI organization
class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def get_group_name(self, dbt_resource_props):
        return dbt_resource_props.get("fqn", [])[1]

    # This ensures dbt tests are mapped to formal Asset Checks
    def get_asset_check_key(self, dbt_resource_props):
        return super().get_asset_check_key(dbt_resource_props)


# 3. CONFIGURE SETTINGS (The Missing Piece)
# We instantiate the translator with specific settings to enable checks.
translator_instance = CustomDagsterDbtTranslator(
    settings=DagsterDbtTranslatorSettings(
        enable_asset_checks=True,
        enable_source_tests_as_checks=True,
    )
)


# 4. The Assets
@dbt_assets(
    manifest=dbt_project.manifest_path,
    dagster_dbt_translator=translator_instance,  # Use the configured instance
    select="fqn:*",
)
def crypto_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # 'build' executes the models and the checks in one atomic step
    yield from dbt.cli(["build", "--select", "fqn:*"], context=context).stream()
