#!/usr/bin/env uv run python
"""Generate dbt seeds/coins_config.csv from config/coins.yaml.

Run: uv run python dbt_project/scripts/generate_seed.py
Or: make generate-seed
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

import yaml

ROOT = Path(__file__).parents[2]
COINS_YAML = ROOT / "config" / "coins.yaml"
SEED_FILE = ROOT / "dbt_project" / "seeds" / "coins_config.csv"


def main():
    with open(COINS_YAML) as f:
        data = yaml.safe_load(f)

    enabled_coins = [c for c in data.get("coins", []) if c.get("enabled", True)]

    lines = ["coin_id,coin_name,symbol"]
    for coin in enabled_coins:
        try:
            lines.append(f"{coin['id']},{coin['name']},{coin['symbol']}")
        except KeyError as e:
            raise ValueError(f"Coin entry missing required field {e}: {coin}") from e

    new_content = "\n".join(lines) + "\n"

    if SEED_FILE.exists() and SEED_FILE.read_text() == new_content:
        print(f"No changes — {SEED_FILE} is up to date ({len(lines) - 1} coins)")
        return

    SEED_FILE.write_text(new_content)
    print(f"Generated {SEED_FILE} ({len(lines) - 1} coins)")


if __name__ == "__main__":
    main()
