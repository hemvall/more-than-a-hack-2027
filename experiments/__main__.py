"""Run fixed baselines locally, or compare two recorded pipeline checks."""

import argparse
import json
import sys
from pathlib import Path

from .runner import ROOT, compare, run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--mode", choices=("supplied", "regenerate"), default="supplied")
    execute.add_argument("--seed", type=int, default=0)
    execute.add_argument("--data-dir", help="Bundle root for regeneration; otherwise MTAH_DATA_DIR or data/")
    execute.add_argument("--runs-dir", type=Path, default=ROOT / "runs" / "experiments")
    execute.add_argument("--allow-dirty", action="store_true", help="Development only; not comparison evidence")
    comparison = commands.add_parser("compare")
    comparison.add_argument("first", type=Path)
    comparison.add_argument("second", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        if not 0 <= args.seed <= 2**32 - 1:
            parser.error("seed must be between 0 and 4294967295")
        if args.data_dir and args.mode != "regenerate":
            parser.error("--data-dir requires --mode regenerate")
        directory = args.runs_dir.resolve()
        if not any(directory.is_relative_to(ROOT / name) for name in ("runs", "artifacts")):
            parser.error("--runs-dir must stay under the repository's ignored runs/ or artifacts/")
    try:
        if args.command == "compare":
            print(json.dumps(compare(args.first, args.second), indent=2, allow_nan=False))
        else:
            path = run(args.mode, args.seed, directory, args.data_dir, args.allow_dirty)
            print(f"Completed local pipeline check: {path}")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"Experiment failed ({type(error).__name__}); inspect the local manifest/logs. "
              "Check clean Git state, inputs and configuration.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
