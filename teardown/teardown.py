"""Delete everything the tutorial created.

    python teardown/teardown.py --yes                      # datasets (incl. model and graph)
    python teardown/teardown.py --yes --delete-connection  # also the BigQuery connection

The Cloud Run service (module 7) is deleted separately:
    gcloud run services delete adk-de-agents --region=<region>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from de_context.bq import client  # noqa: E402
from de_context.config import get_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="confirm deletion")
    parser.add_argument("--delete-connection", action="store_true")
    args = parser.parse_args()

    s = get_settings()
    datasets = s.readable_datasets
    print("This deletes these datasets and all their tables, models and graphs:")
    for d in datasets:
        print(f"  {s.project}.{d}")
    if not args.yes:
        raise SystemExit("Re-run with --yes to confirm.")

    for d in datasets:
        client().delete_dataset(f"{s.project}.{d}", delete_contents=True, not_found_ok=True)
        print(f"  deleted {d}")

    if args.delete_connection:
        subprocess.run(["bq", "rm", "--force", "--connection", s.connection_id], check=False)
        print(f"  deleted connection {s.connection_id}")
    print("Done.")


if __name__ == "__main__":
    main()
