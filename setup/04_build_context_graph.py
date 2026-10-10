"""Step 4: build the lineage/context graph from dbt's manifest.json.

Flattens manifest.json (+ catalog.json if present) and data/glossary.csv into
node and edge tables in the context dataset. With GRAPH_MODE=gql it also
creates a BigQuery property graph over those tables.
"""

from __future__ import annotations

import json

from google.cloud import bigquery

from _common import REPO_ROOT, get_settings, info, run, step
from de_context.bq import client, run_statement
from de_context.graph_builder import TABLE_SCHEMAS, build_rows, property_graph_ddl

DBT_DIR = REPO_ROOT / "dbt_vault"


def load_rows(table: str, rows: list[dict]) -> None:
    s = get_settings()
    schema = [bigquery.SchemaField(c, t) for c, t in TABLE_SCHEMAS[table]]
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    table_id = f"{s.project}.{s.context_dataset}.{table}"
    client().load_table_from_json(rows, table_id, job_config=job_config).result()
    info(f"{table_id}: {len(rows)} rows")


def main() -> None:
    step("Step 4: build the context graph from dbt metadata")
    s = get_settings()
    manifest_path = DBT_DIR / "target" / "manifest.json"
    if not manifest_path.exists():
        run(["dbt", "parse", "--profiles-dir", str(DBT_DIR)], cwd=DBT_DIR)
    manifest = json.loads(manifest_path.read_text())
    catalog_path = DBT_DIR / "target" / "catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else None

    rows = build_rows(manifest, catalog, REPO_ROOT / "data" / "glossary.csv")
    for table, table_rows in rows.items():
        load_rows(table, table_rows)

    if s.graph_mode == "gql":
        ddl = property_graph_ddl(s.context_dataset, s.graph_name)
        run_statement(ddl, label="setup-graph")
        info(f"property graph {s.context_dataset}.{s.graph_name} created")
    else:
        info("GRAPH_MODE=sql: skipping CREATE PROPERTY GRAPH (tools use recursive SQL)")


if __name__ == "__main__":
    main()
