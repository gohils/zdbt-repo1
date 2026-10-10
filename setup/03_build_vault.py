"""Step 3: build the Data Vault and marts with dbt, and produce manifest.json.

dbt reads dataset names from the environment (.env), so this is the same as
running `dbt build` in dbt_vault/ yourself.
"""

from __future__ import annotations

from _common import REPO_ROOT, info, run, step

DBT_DIR = REPO_ROOT / "dbt_vault"


def main() -> None:
    step("Step 3: build the vault and marts with dbt")
    run(["dbt", "build", "--profiles-dir", str(DBT_DIR)], cwd=DBT_DIR)
    # docs generate also writes catalog.json (actual column types from BigQuery)
    run(["dbt", "docs", "generate", "--profiles-dir", str(DBT_DIR)], cwd=DBT_DIR)
    info(f"manifest: {DBT_DIR / 'target' / 'manifest.json'}")


if __name__ == "__main__":
    main()
