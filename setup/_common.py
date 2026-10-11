"""Small helpers shared by the setup scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from de_context.config import get_settings  # noqa: E402


def step(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def info(msg: str) -> None:
    print(f"  - {msg}", flush=True)


def env_for_subprocess() -> dict[str, str]:
    """Environment for dbt / gcloud / bq, including values from .env."""
    get_settings()  # loads .env into os.environ
    return dict(os.environ)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env_for_subprocess(),
        check=check,
        text=True,
        capture_output=capture,
    )
