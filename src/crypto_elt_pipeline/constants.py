from pathlib import Path
from typing import Final

# 1. Project Navigation
# Establishes the repository root based on the source file's depth
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# 2. Local Data Warehouse
# Defines the landing zone for the DuckDB database file
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
DUCKDB_PATH: Final[Path] = DATA_DIR / "crypto.duckdb"

# 3. dbt Orchestration Paths
# Configures the directory and artifacts for the dbt transformation layer
DBT_PROJECT_DIR: Final[Path] = PROJECT_ROOT / "dbt_project"
DBT_TARGET_DIR: Final[Path] = DBT_PROJECT_DIR / "target"
DBT_MANIFEST_PATH: Final[Path] = DBT_TARGET_DIR / "manifest.json"
