from pathlib import Path

# 1. Project Navigation
# Establishes the repository root based on the source file's depth
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 2. Local Data Warehouse
# Defines the landing zone for the DuckDB database file
DATA_DIR = PROJECT_ROOT / "data"
DUCKDB_PATH = DATA_DIR / "crypto.duckdb"

# 3. dbt Orchestration Paths
# Configures the directory and artifacts for the dbt transformation layer
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
DBT_TARGET_DIR = DBT_PROJECT_DIR / "target"
DBT_MANIFEST_PATH = DBT_TARGET_DIR / "manifest.json"
