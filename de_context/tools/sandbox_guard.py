"""A before_tool_callback that only lets write statements touch sandbox datasets.

IAM is the real boundary (the agent identity should only have write access to
the sandbox datasets). This callback is a second line of defence that also
gives the model a clear error message it can act on.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..config import get_settings

_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_READ_START = re.compile(r"^\s*(SELECT|WITH|\(\s*SELECT)\b", re.I)
_TARGET = re.compile(
    r"^\s*(?:"
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"|INSERT\s+(?:INTO\s+)?"
    r"|DELETE\s+(?:FROM\s+)?"
    r"|UPDATE\s+"
    r"|MERGE\s+(?:INTO\s+)?"
    r"|DROP\s+(?:TABLE|VIEW)\s+(?:IF\s+EXISTS\s+)?"
    r"|TRUNCATE\s+TABLE\s+"
    r")(`[^`]+`|[A-Za-z0-9_.\-]+)",
    re.I,
)


def _strip(sql: str) -> str:
    return _COMMENTS.sub(" ", sql or "").strip().rstrip(";").strip()


def check_statement(sql: str, allowed_datasets: set[str]) -> Optional[str]:
    """Return an error message if the statement is not allowed, else None."""
    body = _strip(sql)
    if not body:
        return "Empty statement."
    if ";" in body:
        return "Run one statement per execute_sql call (no multi-statement scripts)."
    if _READ_START.match(body):
        return None
    m = _TARGET.match(body)
    if not m:
        return (
            "Only SELECT queries and CREATE TABLE/VIEW, INSERT, UPDATE, DELETE, MERGE, "
            "DROP TABLE/VIEW or TRUNCATE TABLE on sandbox tables are allowed."
        )
    parts = m.group(1).strip("`").split(".")
    if len(parts) < 2:
        return "Fully qualify the target table as dataset.table (or project.dataset.table)."
    dataset = parts[-2]
    if dataset not in allowed_datasets:
        return (
            f"Writes to dataset '{dataset}' are blocked. The agent may only write to: "
            f"{', '.join(sorted(allowed_datasets))}."
        )
    return None


def sandbox_write_guard(tool: Any, args: dict[str, Any], tool_context: Any) -> Optional[dict]:
    """ADK before_tool_callback: block writes outside the sandbox datasets."""
    if getattr(tool, "name", "") != "execute_sql":
        return None
    s = get_settings()
    error = check_statement(args.get("query", ""), {s.sandbox_dataset})
    if error:
        return {"status": "ERROR", "error_details": f"Blocked by sandbox guard: {error}"}
    return None
