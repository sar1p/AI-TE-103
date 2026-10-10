"""Command-line interface for named diagnostic scenarios and raw facts."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .engine import (
    KnowledgeBaseError,
    _reject_json_constant,
    _unique_object_pairs,
    infer,
    load_knowledge_base,
    knowledge_base_metadata,
)
from .scenarios import DiagnosticScenarioError, load_scenario, load_scenarios


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m expert_system",
        description=(
            "Run the illustrative warehouse diagnostic engine from a named JSON "
            "scenario or a JSON file of raw observations."
        ),
        epilog=(
            "Examples: python -m expert_system --scenario battery-multi-hop; "
            "python -m expert_system --facts facts.json; "
            "python -m expert_system --list-scenarios"
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--scenario",
        metavar="ID",
        help="load a named case from data/diagnostic_scenarios",
    )
    source.add_argument(
        "--facts",
        metavar="PATH",
        help="read a strict JSON object of raw observations; use - for stdin",
    )
    source.add_argument(
        "--list-scenarios",
        action="store_true",
        help="print available named scenario IDs and descriptions as JSON",
    )
    source.add_argument(
        "--all",
        action="store_true",
        help="run every named scenario and print their results as JSON",
    )
    parser.add_argument(
        "--knowledge-base",
        metavar="PATH",
        help="use another schema-validated knowledge-base JSON file",
    )
    parser.add_argument(
        "--output",
        "--output-file",
        dest="output_path",
        metavar="PATH",
        help="write the same JSON export to PATH and stdout",
    )
    return parser


def _load_facts(path_value: str) -> tuple[Any, str]:
    if path_value == "-":
        facts = json.load(
            sys.stdin,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_unique_object_pairs,
        )
        return facts, "stdin"
    path = Path(path_value)
    with path.open("r", encoding="utf-8") as source:
        facts = json.load(
            source,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_unique_object_pairs,
        )
    return facts, _source_label(path)


def _source_label(path: Path) -> str:
    resolved = path.resolve()
    project_root = Path(__file__).resolve().parents[1]
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        return f"external/{resolved.name}"


def _serialize_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def _cli_metadata(knowledge_base: Any) -> dict[str, Any]:
    # Keep evidence collection at the CLI boundary. The engine itself stays
    # independent of the application, planner, and Streamlit modules.
    from interface.evidence import environment_metadata

    return {
        "environment": environment_metadata(),
        "knowledge_base": knowledge_base_metadata(knowledge_base),
    }


def _emit_json(value: dict[str, Any], output_path: str | None) -> None:
    rendered = _serialize_json(value)
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
            output.write("\n")
    print(rendered)


def _scenario_export(scenario: dict[str, Any], knowledge_base: Any) -> tuple[dict[str, Any], bool]:
    facts = scenario["facts"]
    diagnosis = infer(facts, knowledge_base)
    conditions = [finding["condition"] for finding in diagnosis["findings"]]
    matches = (
        diagnosis["status"] == scenario["expected_status"]
        and conditions == scenario["expected_conditions"]
    )
    return (
        {
            "input": {
                "kind": "scenario",
                "id": scenario["id"],
                "title": scenario["title"],
                "source": f"data/diagnostic_scenarios/{scenario['id']}.json",
                "provenance": scenario["provenance"],
                "facts": copy.deepcopy(facts),
            },
            "diagnosis": diagnosis,
            "expected": {
                "status": scenario["expected_status"],
                "conditions": copy.deepcopy(scenario["expected_conditions"]),
            },
            "expectation_match": matches,
        },
        matches,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        knowledge_base = load_knowledge_base(args.knowledge_base)
        metadata = _cli_metadata(knowledge_base)
        if args.list_scenarios:
            scenarios = load_scenarios()
            _emit_json(
                {
                    "metadata": metadata,
                    "scenarios": [
                        {
                            "id": scenario["id"],
                            "title": scenario["title"],
                            "description": scenario["description"],
                        }
                        for scenario in scenarios
                    ]
                },
                args.output_path,
            )
            return 0

        if args.scenario is not None:
            scenario = load_scenario(args.scenario)
            scenario_case, matches = _scenario_export(scenario, knowledge_base)
            result = scenario_case["diagnosis"]
            export = {
                "metadata": metadata,
                **scenario_case,
            }
            expectation_matched = matches
        else:
            if args.all:
                scenarios = load_scenarios()
                cases = []
                expectation_matches = []
                for scenario in scenarios:
                    case, expectation_match = _scenario_export(scenario, knowledge_base)
                    cases.append(case)
                    expectation_matches.append((scenario["id"], expectation_match))
                failed_cases = [
                    scenario_id
                    for scenario_id, expectation_match in expectation_matches
                    if not expectation_match
                ]
                result = {"status": "invalid_input" if failed_cases else "ok"}
                export = {
                    "metadata": metadata,
                    "input": {"kind": "all_scenarios", "count": len(cases)},
                    "cases": cases,
                    "scenario_validation": {
                        "passed": not failed_cases,
                        "failed_ids": failed_cases,
                    },
                }
                expectation_matched = not failed_cases
            else:
                facts, source_name = _load_facts(args.facts)
                result = infer(facts, knowledge_base)
                export = {
                    "metadata": metadata,
                    "input": {
                        "kind": "facts",
                        "source": source_name,
                        "facts": copy.deepcopy(facts),
                    },
                    "diagnosis": result,
                }
                expectation_matched = True
        _emit_json(export, args.output_path)
        if args.all:
            return 0 if expectation_matched else 2
        return 2 if result["status"] == "invalid_input" or not expectation_matched else 0
    except (
        DiagnosticScenarioError,
        KnowledgeBaseError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
