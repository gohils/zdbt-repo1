"""Step 1: create the demo datasets."""

from __future__ import annotations

from google.cloud import bigquery

from _common import get_settings, info, step
from de_context.bq import client

SANDBOX_EXPIRATION_MS = 7 * 24 * 60 * 60 * 1000  # synthetic data policy: 7 days


def main() -> None:
    step("Step 1: create datasets")
    s = get_settings()
    descriptions = {
        s.source_dataset: "Fake source system tables (CRM, web shop) loaded in batches",
        s.vault_dataset: "dbt Data Vault: staging views, hubs, links, satellites",
        s.mart_dataset: "Information marts built from the vault",
        s.context_dataset: "Agent context: document embeddings and lineage graph",
        s.sandbox_dataset: "Synthetic source data written by the synthetic data agent",
        s.sandbox_vault_dataset: "dbt vault built from synthetic sandbox data",
    }
    for name, desc in descriptions.items():
        ds = bigquery.Dataset(f"{s.project}.{name}")
        ds.location = s.bq_location
        ds.description = desc
        ds.labels = {"app": "adk-bq-context-demo"}
        if name in (s.sandbox_dataset, s.sandbox_vault_dataset):
            ds.default_table_expiration_ms = SANDBOX_EXPIRATION_MS
        client().create_dataset(ds, exists_ok=True)
        info(f"{s.project}.{name} ({s.bq_location})")


if __name__ == "__main__":
    main()
