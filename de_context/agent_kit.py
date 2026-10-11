"""Helpers shared by all agents: the BigQuery toolset and prompt loading."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Callable

import google.auth

try:  # ADK >= 2.x
    from google.adk.integrations.bigquery import BigQueryCredentialsConfig, BigQueryToolset
    from google.adk.integrations.bigquery.config import BigQueryToolConfig, WriteMode
except ImportError:  # older ADK releases
    from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
    from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

from .config import get_settings

# Only the core tools: metadata and SQL. Keeps the tool list small and focused.
CORE_BQ_TOOLS = [
    "list_dataset_ids",
    "get_dataset_info",
    "list_table_ids",
    "get_table_info",
    "execute_sql",
]


def bigquery_toolset(allow_writes: bool = False) -> BigQueryToolset:
    """ADK's first-party BigQuery toolset using Application Default Credentials.

    Locally that is the developer's own login (gcloud auth application-default
    login); on Cloud Run it is the service's service account.
    """
    s = get_settings()
    credentials, _ = google.auth.default()
    config = BigQueryToolConfig(
        write_mode=WriteMode.ALLOWED if allow_writes else WriteMode.BLOCKED,
        maximum_bytes_billed=s.max_bytes_billed,
        max_query_result_rows=100,
        application_name="adk-bq-context-demo",
        location=s.bq_location,
    )
    return BigQueryToolset(
        tool_filter=CORE_BQ_TOOLS,
        credentials_config=BigQueryCredentialsConfig(credentials=credentials),
        bigquery_tool_config=config,
    )


def load_prompt(agent_file: str, name: str = "prompt.md") -> Callable[..., str]:
    """Load the prompt file next to an agent and fill in ${placeholders}.

    Returned as an instruction provider (a function) so ADK does not try to
    treat curly braces in SQL examples as session-state placeholders.
    """
    s = get_settings()
    text = (Path(agent_file).parent / name).read_text(encoding="utf-8")
    common = (Path(__file__).parent / "common_rules.md").read_text(encoding="utf-8")
    text = text.replace("${common_rules}", common)
    rendered = Template(text).safe_substitute(
        project=s.project,
        source_dataset=s.source_dataset,
        vault_dataset=s.vault_dataset,
        mart_dataset=s.mart_dataset,
        context_dataset=s.context_dataset,
        sandbox_dataset=s.sandbox_dataset,
        sandbox_vault_dataset=s.sandbox_vault_dataset,
        graph_mode=s.graph_mode,
    )

    def provider(_context=None) -> str:
        return rendered

    return provider
