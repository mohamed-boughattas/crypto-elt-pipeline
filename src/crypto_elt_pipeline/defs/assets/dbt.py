from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import (
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    DbtProject,
    dbt_assets,
)

# 1. dbt Project Initialization
# Resolves the project path and prepares the manifest during development.
DBT_PROJECT_DIR = Path(__file__).parents[4] / "dbt_project"
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()


# 2. Custom Metadata Translator
# Organizes the Dagster UI by grouping assets based on their dbt FQN.
class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def get_group_name(self, dbt_resource_props):
        # fqn[1] is the top-level folder under 'models/'
        folder = dbt_resource_props.get("fqn", [])[1]

        group_mapping = {"raw": "Bronze", "staging": "Silver", "marts": "Gold"}
        return group_mapping.get(folder, "Default")

    # Maps dbt tests to native Dagster Asset Checks.
    def get_asset_check_key(self, dbt_resource_props):
        return super().get_asset_check_key(dbt_resource_props)


# 3. Translator Settings
# Configures the translator to expose both model and source tests as checks.
translator_instance = CustomDagsterDbtTranslator(
    settings=DagsterDbtTranslatorSettings(
        enable_asset_checks=True,
        enable_source_tests_as_checks=True,
    )
)


# 4. dbt Asset Definitions
# Materializes dbt models and executes tests using the Select-based build command.
@dbt_assets(
    manifest=dbt_project.manifest_path,
    dagster_dbt_translator=translator_instance,
    select="fqn:*",
)
def crypto_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # 'build' runs models and checks atomically; results are streamed to the UI.
    yield from dbt.cli(["build", "--select", "fqn:*"], context=context).stream()
