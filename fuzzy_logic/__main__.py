"""Command-line entry point for ``python -m fuzzy_logic``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import FuzzyInputError, evaluate_speed, evaluate_sugeno_speed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate an illustrative fuzzy speed controller.")
    parser.add_argument("--clearance", required=True, type=float, help="clearance in cells, from 0 to 5")
    parser.add_argument("--battery", required=True, type=float, help="battery percentage, from 0 to 100")
    parser.add_argument(
        "--method",
        choices=("mamdani", "sugeno"),
        default="mamdani",
        help="inference method (default: mamdani)",
    )
    parser.add_argument("--output", type=Path, help="write the JSON result to this file")
    args = parser.parse_args(argv)

    evaluator = evaluate_speed if args.method == "mamdani" else evaluate_sugeno_speed
    try:
        result = evaluator(args.clearance, args.battery)
    except FuzzyInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        sys.stdout.write(payload)
        return 0
    try:
        args.output.write_text(payload, encoding="utf-8")
    except OSError as error:
        print(f"error: could not write JSON output: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
