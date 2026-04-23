from pathlib import Path
from typing import Final

# 1. Project Navigation
# Establishes the repository root based on the source file's depth
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# 2. Local Data Warehouse
# Defines the landing zone for the DuckDB database file
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
DUCKDB_PATH: Final[Path] = DATA_DIR / "crypto.duckdb"

# 3. Logging Paths
# Configures the directory for application and connector logs
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"

# 4. dbt Orchestration Paths
# Configures the directory for the dbt transformation layer
DBT_PROJECT_DIR: Final[Path] = PROJECT_ROOT / "dbt_project"
