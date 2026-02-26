from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str | None:
        """Get the group name for a dbt resource based on its folder structure.

        Args:
            dbt_resource_props: Dictionary containing dbt resource properties including FQN

        Returns:
            Group name for UI organization, or None to use default grouping
        """
        # fqn[1] is the top-level folder under 'models/'
        folder = dbt_resource_props.get("fqn", [])[1] if dbt_resource_props.get("fqn") else None

        group_mapping = {"raw": "Bronze", "staging": "Silver", "marts": "Gold"}
        return group_mapping.get(folder, "Default") if folder else None


# 3. Translator Settings
# Configures the translator to enable asset checks and disable source tests to avoid partitioning issues.
translator_instance = CustomDagsterDbtTranslator(
    settings=DagsterDbtTranslatorSettings(
        enable_asset_checks=True,
        enable_source_tests_as_checks=False,
    )
)


# 4. dbt Asset Definitions
# Materializes dbt models and executes tests using the Select-based build command.
@dbt_assets(
    manifest=dbt_project.manifest_path,
    dagster_dbt_translator=translator_instance,
    select="fqn:*",
)
def crypto_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Any:
    # 'build' runs models and checks atomically; results are streamed to the UI.
    yield from dbt.cli(["build", "--select", "fqn:*"], context=context).stream()
