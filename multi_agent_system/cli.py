"""Standalone JSON replay for the bounded fleet simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scenarios import crossing_scenario


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("ticks must be a nonnegative integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("ticks must be a nonnegative integer")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the bounded warehouse fleet scenario.")
    parser.add_argument("--ticks", required=True, type=_nonnegative_int)
    parser.add_argument("--output", type=Path, help="write the JSON replay to this path")
    args = parser.parse_args(argv)

    simulation = crossing_scenario()
    for _ in range(args.ticks):
        simulation.tick()
    output = {
        "scenario": "crossing",
        "ticks_run": simulation.tick_count,
        "final": simulation.snapshot(),
        "messages": simulation.messages,
    }
    rendered = json.dumps(output, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
        return 0
    try:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    except OSError as error:
        parser.error(f"cannot write output file: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
