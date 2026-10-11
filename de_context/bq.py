"""BigQuery helpers with cost guardrails and job labels."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable

from google.cloud import bigquery

from .config import get_settings

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_\-.]+$")


@lru_cache(maxsize=1)
def client() -> bigquery.Client:
    s = get_settings()
    return bigquery.Client(project=s.project, location=s.bq_location)


def _param(name: str, value: Any) -> bigquery.ScalarQueryParameter:
    if isinstance(value, bool):
        kind = "BOOL"
    elif isinstance(value, int):
        kind = "INT64"
    elif isinstance(value, float):
        kind = "FLOAT64"
    else:
        kind = "STRING"
    return bigquery.ScalarQueryParameter(name, kind, value)


def run_query(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    label: str = "de-context-tool",
    max_bytes_billed: int | None = None,
) -> list[dict[str, Any]]:
    """Run a query and return rows as plain dicts.

    Every query carries a byte cap and a job label so cost and usage can be
    traced in INFORMATION_SCHEMA.JOBS.
    """
    s = get_settings()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[_param(k, v) for k, v in (params or {}).items()],
        maximum_bytes_billed=max_bytes_billed or s.max_bytes_billed,
        labels={"app": "adk-bq-context-demo", "component": label},
    )
    job = client().query(sql, job_config=job_config)
    return [dict(row.items()) for row in job.result()]


def run_statement(sql: str, *, label: str = "de-context-setup") -> None:
    """Run a DDL/DML statement (used by setup scripts, not by agents)."""
    s = get_settings()
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=s.max_bytes_billed * 10,
        labels={"app": "adk-bq-context-demo", "component": label},
    )
    client().query(sql, job_config=job_config).result()


def safe_identifier(value: str) -> str:
    """Validate a value before it is inlined into SQL/GQL text.

    Only letters, digits, underscore, dash and dot are allowed. Tool inputs that
    end up in query text always pass through here; everything else is a query
    parameter.
    """
    if not value or not _IDENTIFIER.match(value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


def compact(rows: Iterable[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    """Trim results so tools return compact context to the model."""
    out = []
    for i, row in enumerate(rows):
        if i >= limit:
            break
        out.append({k: (str(v) if not isinstance(v, (int, float, bool, type(None), str)) else v) for k, v in row.items()})
    return out
