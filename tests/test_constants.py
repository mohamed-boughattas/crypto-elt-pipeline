"""Unit tests for the constants module."""

from crypto_elt_pipeline.constants import (
    DATA_DIR,
    DBT_MANIFEST_PATH,
    DBT_PROJECT_DIR,
    DBT_TARGET_DIR,
    DUCKDB_PATH,
    PROJECT_ROOT,
)


class TestProjectPaths:
    """Tests for project path constants."""

    def test_project_root_exists(self):
        """Verify PROJECT_ROOT points to a valid directory."""
        assert PROJECT_ROOT.exists(), f"PROJECT_ROOT {PROJECT_ROOT} does not exist"
        assert PROJECT_ROOT.is_dir(), f"PROJECT_ROOT {PROJECT_ROOT} is not a directory"

    def test_project_root_contains_pyproject(self):
        """Verify PROJECT_ROOT contains pyproject.toml."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found in PROJECT_ROOT"

    def test_data_dir_path(self):
        """Verify DATA_DIR is correctly constructed."""
        assert DATA_DIR == PROJECT_ROOT / "data"
        assert DATA_DIR.name == "data"

    def test_duckdb_path_format(self):
        """Verify DUCKDB_PATH ends with .duckdb extension."""
        assert str(DUCKDB_PATH).endswith(".duckdb")
        assert DUCKDB_PATH.name == "crypto.duckdb"

    def test_duckdb_path_parent_is_data_dir(self):
        """Verify DUCKDB_PATH parent is DATA_DIR."""
        assert DUCKDB_PATH.parent == DATA_DIR

    def test_dbt_project_dir_exists(self):
        """Verify DBT_PROJECT_DIR exists."""
        assert DBT_PROJECT_DIR.exists(), f"DBT_PROJECT_DIR {DBT_PROJECT_DIR} does not exist"
        assert DBT_PROJECT_DIR.is_dir(), f"DBT_PROJECT_DIR {DBT_PROJECT_DIR} is not a directory"

    def test_dbt_project_dir_contains_config(self):
        """Verify DBT_PROJECT_DIR contains dbt_project.yml."""
        dbt_config = DBT_PROJECT_DIR / "dbt_project.yml"
        assert dbt_config.exists(), "dbt_project.yml not found in DBT_PROJECT_DIR"

    def test_dbt_target_dir_path(self):
        """Verify DBT_TARGET_DIR is correctly constructed."""
        assert DBT_TARGET_DIR == DBT_PROJECT_DIR / "target"
        assert DBT_TARGET_DIR.name == "target"

    def test_dbt_manifest_path_format(self):
        """Verify DBT_MANIFEST_PATH ends with manifest.json."""
        assert str(DBT_MANIFEST_PATH).endswith("manifest.json")
        assert DBT_MANIFEST_PATH.name == "manifest.json"

    def test_dbt_manifest_path_parent_is_target_dir(self):
        """Verify DBT_MANIFEST_PATH parent is DBT_TARGET_DIR."""
        assert DBT_MANIFEST_PATH.parent == DBT_TARGET_DIR


class TestPathRelationships:
    """Tests for relationships between path constants."""

    def test_data_dir_is_within_project_root(self):
        """Verify DATA_DIR is within PROJECT_ROOT."""
        assert DATA_DIR.is_relative_to(PROJECT_ROOT)

    def test_duckdb_path_is_within_data_dir(self):
        """Verify DUCKDB_PATH is within DATA_DIR."""
        assert DUCKDB_PATH.is_relative_to(DATA_DIR)

    def test_dbt_project_dir_is_within_project_root(self):
        """Verify DBT_PROJECT_DIR is within PROJECT_ROOT."""
        assert DBT_PROJECT_DIR.is_relative_to(PROJECT_ROOT)

    def test_all_paths_share_common_root(self):
        """Verify all paths share PROJECT_ROOT as common ancestor."""
        paths = [
            DATA_DIR,
            DUCKDB_PATH,
            DBT_PROJECT_DIR,
            DBT_TARGET_DIR,
            DBT_MANIFEST_PATH,
        ]
        for path in paths:
            assert path.is_relative_to(PROJECT_ROOT), f"{path} is not relative to PROJECT_ROOT"
