# dbt Conventions

## Project layout
- `models/staging`: one view per source table, named `stg_<source_table>`, plus `_sources.yml` and `_staging.yml`.
- `models/raw_vault`: hubs, links and satellites, materialized as tables, documented in `_raw_vault.yml`.
- `models/marts`: dimensions and facts, documented in `_marts.yml`.
- Macros for hashing live in `macros/hashing.sql`.

## SQL style
- Lower-case SQL keywords in models; CTEs named for what they contain (`deduped`, `changes`, `current_orders`).
- One model per file. The final SELECT lists columns explicitly; no `SELECT *` in the final SELECT of a model.
- Use `{{ ref() }}` and `{{ source() }}`; never hard-code dataset names.
- Use `qualify row_number() over (...) = 1` for "first seen" and "current version" logic.

## Documentation
- Every model and every column has a description and a `data_type` in YAML.
- Descriptions say what a row represents and how the column is derived.

## Tests
- Declare foreign keys with `relationships` tests, including on sources (with severity `warn`). These tests also feed the team's lineage and join-path graph, so undeclared relationships are invisible to tools and agents.
- Use `accepted_values` for status and category columns.
- Use the new test syntax with `arguments:` (dbt 1.10+).

## Environments
- Dataset names come from environment variables (`BQ_SOURCE_DATASET`, `BQ_VAULT_DATASET`, `BQ_MART_DATASET`).
- To build a sandbox vault from synthetic data, point the variables at the sandbox datasets:
  `BQ_SOURCE_DATASET=demo_sandbox BQ_VAULT_DATASET=demo_sandbox_vault BQ_MART_DATASET=demo_sandbox_vault dbt build`.
