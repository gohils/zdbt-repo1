"""Step 0: check tools, configuration and access before creating anything."""

from __future__ import annotations

import shutil
import sys

from _common import get_settings, info, step


def main() -> None:
    step("Step 0: check prerequisites")
    ok = True

    if sys.version_info < (3, 10):
        print("  ! Python 3.10+ is required")
        ok = False

    s = get_settings()
    info(f"project={s.project}  bq_location={s.bq_location}  vertex_location={s.vertex_location}")
    info(f"agent_model={s.agent_model}  embedding={s.embedding_endpoint}  graph_mode={s.graph_mode}")

    for tool in ("gcloud", "bq", "dbt"):
        if shutil.which(tool):
            info(f"{tool}: found")
        else:
            print(f"  ! {tool} not found on PATH")
            ok = False

    try:
        import google.auth

        creds, project = google.auth.default()
        info(f"Application Default Credentials: found (quota project: {project})")
    except Exception as exc:  # pragma: no cover - environment specific
        print(f"  ! No Application Default Credentials: {exc}")
        print("    Run: gcloud auth application-default login")
        ok = False

    if ok:
        try:
            from de_context.bq import client

            list(client().list_datasets(max_results=1))
            info("BigQuery access: OK")
        except Exception as exc:  # pragma: no cover
            print(f"  ! BigQuery access failed: {str(exc)[:300]}")
            print("    Check that the BigQuery API is enabled and you have BigQuery User/Data Editor roles.")
            ok = False

    if not ok:
        raise SystemExit("Prerequisite check failed. Fix the items marked with '!' and re-run.")
    info("All prerequisites OK")


if __name__ == "__main__":
    main()
