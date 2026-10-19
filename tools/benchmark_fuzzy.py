#!/usr/bin/env python3
"""Export a fixed fuzzy response surface and alternated-order API timing samples."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter_ns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fuzzy_logic import configuration, evaluate_speed, evaluate_sugeno_speed
from interface.evidence import environment_metadata


def benchmark(repeats: int) -> tuple[list[dict], list[dict], dict]:
    if type(repeats) is not int or not 1 <= repeats <= 100:
        raise ValueError("repeats must be an integer between 1 and 100")
    evaluators = {"mamdani": evaluate_speed, "sugeno": evaluate_sugeno_speed}
    surface, samples = [], []
    for case_id, (clearance, battery) in enumerate(
        ( (index / 2, level) for index in range(11) for level in range(0, 101, 10) )
    ):
        row = {"clearance_cells": clearance, "battery_percent": battery}
        for name, evaluator in evaluators.items():
            result = evaluator(clearance, battery)
            row[f"{name}_speed_percent"] = result["output"]["speed_percent"]
        surface.append(row)
        for repetition in range(repeats):
            order = list(evaluators)
            if (case_id + repetition) % 2:
                order.reverse()
            for order_index, name in enumerate(order):
                started = perf_counter_ns()
                result = evaluators[name](clearance, battery)
                elapsed_ns = perf_counter_ns() - started
                samples.append({
                    "case_id": case_id, "clearance_cells": clearance,
                    "battery_percent": battery, "repetition": repetition,
                    "order_index": order_index, "method": name, "elapsed_ns": elapsed_ns,
                    "speed_percent": result["output"]["speed_percent"],
                })
    canonical = json.dumps(configuration(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    summary = {
        "metadata": environment_metadata(),
        "configuration_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "case_count": len(surface), "repeats": repeats, "timing_sample_count": len(samples),
        "median_api_elapsed_ns": {
            name: median(row["elapsed_ns"] for row in samples if row["method"] == name)
            for name in evaluators
        },
        "measurement_scope": "One full public evaluator call, including memberships and proof construction; excludes file I/O and rendering.",
        "order": "Alternates method order by case and repetition; untimed evaluation warms each case.",
        "limitations": [
            "Synthetic inputs and one host do not establish field accuracy or universal latency.",
            "Mamdani returns a sampled aggregation curve; Sugeno has no such output set.",
            "The methods have different output semantics; timing does not select the better controller.",
            "The surface samples inputs; it is not a calibrated operating envelope or a monotonicity proof.",
        ],
    }
    return surface, samples, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("artifacts/fuzzy-benchmark"))
    args = parser.parse_args(argv)
    try:
        surface, samples, summary = benchmark(args.repeats)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, rows in (("response-surface.csv", surface), ("timing-samples.csv", samples)):
            with (args.output / name).open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
        )
    except (OSError, ValueError) as error:
        print(f"Fuzzy benchmark failed: {error}", file=sys.stderr)
        return 2
    print(f"Fuzzy benchmark: {len(surface)} cases, {len(samples)} timing samples in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
