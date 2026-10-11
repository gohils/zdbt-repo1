"""Settings for the demo, read from environment variables (and a .env file).

The same code runs on a laptop and on Cloud Run: only these values change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    # Prefer a .env found from the current directory upwards, then the repo root.
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found, override=False)
    repo_env = REPO_ROOT / ".env"
    if repo_env.exists():
        load_dotenv(repo_env, override=False)


@dataclass(frozen=True)
class Settings:
    project: str
    vertex_location: str
    bq_location: str
    source_dataset: str
    vault_dataset: str
    mart_dataset: str
    context_dataset: str
    sandbox_dataset: str
    sandbox_vault_dataset: str
    bq_connection: str
    agent_model: str
    embedding_endpoint: str
    max_bytes_billed: int
    graph_mode: str
    graph_name: str
    generated_dir: Path

    # Fully qualified names -------------------------------------------------
    def table(self, dataset: str, name: str) -> str:
        return f"`{self.project}.{dataset}.{name}`"

    def ctx(self, name: str) -> str:
        return self.table(self.context_dataset, name)

    @property
    def embedding_model(self) -> str:
        return self.ctx("embedding_model")

    @property
    def graph(self) -> str:
        return f"`{self.project}.{self.context_dataset}.{self.graph_name}`"

    @property
    def connection_id(self) -> str:
        return f"{self.project}.{self.bq_location}.{self.bq_connection}"

    @property
    def readable_datasets(self) -> list[str]:
        return [
            self.source_dataset,
            self.vault_dataset,
            self.mart_dataset,
            self.context_dataset,
            self.sandbox_dataset,
            self.sandbox_vault_dataset,
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not set. Copy .env.example to .env and fill it in."
        )
    graph_mode = os.environ.get("GRAPH_MODE", "sql").strip().lower()
    if graph_mode not in ("gql", "sql"):
        raise RuntimeError("GRAPH_MODE must be 'gql' or 'sql'")
    max_bytes = int(os.environ.get("MAX_BYTES_BILLED", "1073741824"))
    if max_bytes < 10_485_760:
        raise RuntimeError("MAX_BYTES_BILLED must be at least 10485760 (10 MB)")
    generated_dir = Path(os.environ.get("GENERATED_DIR", "generated"))
    if not generated_dir.is_absolute():
        generated_dir = REPO_ROOT / generated_dir
    return Settings(
        project=project,
        vertex_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        bq_location=os.environ.get("BQ_LOCATION", "US"),
        source_dataset=os.environ.get("BQ_SOURCE_DATASET", "demo_source"),
        vault_dataset=os.environ.get("BQ_VAULT_DATASET", "demo_vault"),
        mart_dataset=os.environ.get("BQ_MART_DATASET", "demo_mart"),
        context_dataset=os.environ.get("BQ_CONTEXT_DATASET", "demo_context"),
        sandbox_dataset=os.environ.get("BQ_SANDBOX_DATASET", "demo_sandbox"),
        sandbox_vault_dataset=os.environ.get(
            "BQ_SANDBOX_VAULT_DATASET", "demo_sandbox_vault"
        ),
        bq_connection=os.environ.get("BQ_CONNECTION", "vertex_conn"),
        agent_model=os.environ.get("AGENT_MODEL", "gemini-3.5-flash"),
        embedding_endpoint=os.environ.get("EMBEDDING_ENDPOINT", "text-embedding-005"),
        max_bytes_billed=max_bytes,
        graph_mode=graph_mode,
        graph_name=os.environ.get("GRAPH_NAME", "lineage_graph"),
        generated_dir=generated_dir,
    )
