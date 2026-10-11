"""Run the whole setup (or resume from a step):

    python setup/run_all.py            # steps 0-5
    python setup/run_all.py --from-step 4
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    "00_check_prereqs.py",
    "01_create_datasets.py",
    "02_load_source_data.py",
    "03_build_vault.py",
    "04_build_context_graph.py",
    "05_build_doc_embeddings.py",
]


def run_step(filename: str) -> None:
    spec = importlib.util.spec_from_file_location(filename[:-3], HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-step", type=int, default=0, help="first step to run (0-5)")
    parser.add_argument("--to-step", type=int, default=len(STEPS) - 1, help="last step to run (0-5)")
    args = parser.parse_args()
    for i, filename in enumerate(STEPS):
        if args.from_step <= i <= args.to_step:
            run_step(filename)
    print("\nSetup complete. Next: cd agents && adk web")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(HERE))
    main()
