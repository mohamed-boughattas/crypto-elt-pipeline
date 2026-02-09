from pathlib import Path

# 1. Project Geography
# We start from this file's location and go up to the repo root
# src/crypto_elt_pipeline/constants.py -> src/crypto_elt_pipeline -> src -> REPO_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 2. Data Storage Paths
DATA_DIR = PROJECT_ROOT / "data"
DUCKDB_PATH = DATA_DIR / "crypto.duckdb"

# 3. dbt Project Paths
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
DBT_TARGET_DIR = DBT_PROJECT_DIR / "target"
DBT_MANIFEST_PATH = DBT_TARGET_DIR / "manifest.json"
