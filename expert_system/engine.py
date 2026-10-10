"""Schema-checked, illustrative forward chaining for warehouse diagnostics.

The knowledge base is external JSON so its observations, rules, and provenance
can be reviewed without importing Python code. Each diagnosis uses a fresh set
of raw facts and a fresh forward-chaining session.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class KnowledgeBaseError(ValueError):
    """Raised when the external rule data is missing or inconsistent."""


@dataclass(frozen=True)
class Rule:
    id: str
    validation: str
    premises: dict[str, Any]
    conclusion: dict[str, Any]
    reason: str
    expose_finding: bool
    recommendations: tuple[dict[str, str], ...]

    @property
    def derived_value(self) -> Any:
        return self.conclusion.get("value", True)


@dataclass(frozen=True)
class DiagnosticGroup:
    id: str
    observations: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeBase:
    """Validated JSON data used by one inference run."""

    provenance: str
    observations: dict[str, dict[str, Any]]
    required_observations: tuple[str, ...]
    groups: tuple[DiagnosticGroup, ...]
    rules: tuple[Rule, ...]
    document: dict[str, Any]
    schema_version: int = 1
    source_path: str | None = None
    source_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return an isolated JSON-shaped copy for callers and fixture tests."""
        return copy.deepcopy(self.document)


_KB_PATH = Path(__file__).with_name("knowledge_base.json")
_KB_KEYS = {
    "schema_version",
    "provenance",
    "required_observations",
    "observations",
    "groups",
    "rules",
}
_OBSERVATION_TYPES = {"string", "integer", "number", "boolean"}


def _empty_result(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": [],
    }


def _is_json_value(value: Any, active: set[int] | None = None) -> bool:
    """Check strict finite JSON data, rejecting tuples, custom types, and cycles."""
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) not in (list, dict):
        return False
    if active is None:
        active = set()
    identity = id(value)
    if identity in active:
        return False
    active.add(identity)
    try:
        if type(value) is list:
            return all(_is_json_value(item, active) for item in value)
        return all(
            type(key) is str and _is_json_value(item, active)
            for key, item in value.items()
        )
    finally:
        active.remove(identity)


def _typed_equal(left: Any, right: Any) -> bool:
    """Compare JSON scalars without Python's bool/int equality overlap."""
    return type(left) is type(right) and left == right


def _is_scalar(value: Any) -> bool:
    return value is not None and type(value) in (str, bool, int, float) and (
        type(value) is not float or math.isfinite(value)
    )


def _matches_type(value: Any, declared_type: str) -> bool:
    if declared_type == "string":
        return type(value) is str
    if declared_type == "integer":
        return type(value) is int
    if declared_type == "number":
        return type(value) in (int, float) and (
            type(value) is not float or math.isfinite(value)
        )
    if declared_type == "boolean":
        return type(value) is bool
    return False


def _has_exact_keys(value: Any, expected: set[str]) -> bool:
    return type(value) is dict and set(value) == expected


def validate_knowledge_base(payload: Any) -> KnowledgeBase:
    """Validate external rule data and return a normalized, isolated knowledge base.

    Rules may refer to derived facts declared by any rule, including cyclic
    dependencies. Inference uses grounded facts and fires each rule ID at most
    once, so cycles cannot create unbounded work. Conflicting assignments are
    rejected here before a diagnosis can run.
    """
    if type(payload) is not dict or not _is_json_value(payload):
        raise KnowledgeBaseError("Knowledge base must be a finite JSON object.")
    document = copy.deepcopy(payload)
    if set(document) != _KB_KEYS:
        raise KnowledgeBaseError(
            "Knowledge base must contain exactly schema_version, provenance, "
            "required_observations, observations, groups, and rules."
        )
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise KnowledgeBaseError("Knowledge base schema_version must be integer 1.")
    provenance = document["provenance"]
    if (
        type(provenance) is not str
        or not provenance.strip()
        or "illustrative" not in provenance.lower()
    ):
        raise KnowledgeBaseError(
            "Knowledge base provenance must explicitly label the rules illustrative."
        )

    observations_data = document["observations"]
    if type(observations_data) is not dict or not observations_data:
        raise KnowledgeBaseError("Knowledge base observations must be a nonempty object.")
    observations: dict[str, dict[str, Any]] = {}
    for name, spec in observations_data.items():
        if type(name) is not str or not name.strip() or not _has_exact_keys(
            spec, {"type", "allowed_values"}
        ):
            raise KnowledgeBaseError(
                "Each observation needs a name, declared type, and allowed_values."
            )
        declared_type = spec["type"]
        values = spec["allowed_values"]
        if type(declared_type) is not str or declared_type not in _OBSERVATION_TYPES:
            raise KnowledgeBaseError(
                f"Observation {name!r} has unsupported declared type {declared_type!r}."
            )
        if type(values) is not list or not values:
            raise KnowledgeBaseError(
                f"Observation {name!r} must declare at least one allowed value."
            )
        seen_values: list[Any] = []
        for value in values:
            if not _is_scalar(value) or not _matches_type(value, declared_type):
                raise KnowledgeBaseError(
                    f"Observation {name!r} has a value inconsistent with type {declared_type!r}."
                )
            if any(_typed_equal(value, prior) for prior in seen_values):
                raise KnowledgeBaseError(
                    f"Observation {name!r} repeats an allowed value."
                )
            seen_values.append(value)
        observations[name] = {
            "type": declared_type,
            "allowed_values": tuple(copy.deepcopy(values)),
        }

    required_data = document["required_observations"]
    if type(required_data) is not list or not required_data:
        raise KnowledgeBaseError("required_observations must be a nonempty list.")
    if any(type(name) is not str or name not in observations for name in required_data):
        raise KnowledgeBaseError(
            "Every required observation must be declared in observations."
        )
    if len(set(required_data)) != len(required_data):
        raise KnowledgeBaseError("required_observations must not contain duplicates.")
    required = tuple(required_data)

    groups_data = document["groups"]
    if type(groups_data) is not list:
        raise KnowledgeBaseError("groups must be a list.")
    groups: list[DiagnosticGroup] = []
    seen_group_ids: set[str] = set()
    grouped_observations: set[str] = set()
    required_set = set(required)
    for group in groups_data:
        if not _has_exact_keys(group, {"id", "observations"}):
            raise KnowledgeBaseError("Each diagnostic group needs id and observations.")
        group_id, members = group["id"], group["observations"]
        if (
            type(group_id) is not str
            or not group_id.strip()
            or group_id in seen_group_ids
        ):
            raise KnowledgeBaseError("Diagnostic group IDs must be unique nonempty strings.")
        if type(members) is not list or not members:
            raise KnowledgeBaseError(f"Diagnostic group {group_id!r} must not be empty.")
        if any(type(name) is not str or name not in observations for name in members):
            raise KnowledgeBaseError(
                f"Diagnostic group {group_id!r} refers to an undeclared observation."
            )
        if len(set(members)) != len(members):
            raise KnowledgeBaseError(
                f"Diagnostic group {group_id!r} repeats an observation."
            )
        if any(name in required_set for name in members):
            raise KnowledgeBaseError(
                f"Diagnostic group {group_id!r} cannot include a required observation."
            )
        if grouped_observations.intersection(members):
            raise KnowledgeBaseError(
                "Each optional observation may belong to only one diagnostic group."
            )
        seen_group_ids.add(group_id)
        grouped_observations.update(members)
        groups.append(DiagnosticGroup(group_id, tuple(members)))

    rules_data = document["rules"]
    if type(rules_data) is not list or not rules_data:
        raise KnowledgeBaseError("rules must be a nonempty list.")
    rule_ids: set[str] = set()
    derived_values: dict[str, Any] = {}
    parsed_rules: list[Rule] = []
    for rule_data in rules_data:
        expected_rule_keys = {
            "id",
            "validation",
            "premises",
            "conclusion",
            "reason",
            "expose_finding",
            "recommendations",
        }
        if not _has_exact_keys(rule_data, expected_rule_keys):
            raise KnowledgeBaseError(
                "Each rule must contain exactly id, validation, premises, conclusion, "
                "reason, expose_finding, and recommendations."
            )
        rule_id = rule_data["id"]
        if type(rule_id) is not str or not rule_id.strip() or rule_id in rule_ids:
            raise KnowledgeBaseError("Rule IDs must be unique nonempty strings.")
        rule_ids.add(rule_id)
        if rule_data["validation"] != "illustrative":
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} must be labeled illustrative."
            )
        reason = rule_data["reason"]
        if type(reason) is not str or not reason.strip() or "illustrative" not in reason.lower():
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} needs an explanatory reason labeled illustrative."
            )
        premises = rule_data["premises"]
        conclusion = rule_data["conclusion"]
        if type(premises) is not dict or not premises:
            raise KnowledgeBaseError(f"Rule {rule_id!r} needs at least one premise.")
        if type(conclusion) is not dict or set(conclusion) not in (
            {"condition"}, {"condition", "value"}, {"condition", "pause_robot"},
            {"condition", "value", "pause_robot"},
        ):
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} conclusion needs condition, optional value, "
                "and optional pause_robot."
            )
        condition = conclusion.get("condition")
        derived_value = conclusion.get("value", True)
        if (
            type(condition) is not str
            or not condition.strip()
            or condition in observations
        ):
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} must derive a non-raw condition name."
            )
        if not _is_scalar(derived_value):
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} conclusion value must be a finite JSON scalar."
            )
        if "pause_robot" in conclusion and type(conclusion["pause_robot"]) is not bool:
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} pause_robot must be boolean when present."
            )
        previous_value = derived_values.get(condition, _MISSING)
        if previous_value is not _MISSING and not _typed_equal(previous_value, derived_value):
            raise KnowledgeBaseError(
                f"Rules assign conflicting values to derived fact {condition!r}."
            )
        derived_values[condition] = copy.deepcopy(derived_value)

        expose_finding = rule_data["expose_finding"]
        if type(expose_finding) is not bool:
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} expose_finding must be boolean."
            )
        recommendations_data = rule_data["recommendations"]
        if type(recommendations_data) is not list:
            raise KnowledgeBaseError(
                f"Rule {rule_id!r} recommendations must be a list."
            )
        recommendations: list[dict[str, str]] = []
        for recommendation in recommendations_data:
            if not _has_exact_keys(recommendation, {"action", "reason"}):
                raise KnowledgeBaseError(
                    f"Rule {rule_id!r} recommendation needs action and reason."
                )
            action, text = recommendation["action"], recommendation["reason"]
            if (
                type(action) is not str
                or not action.strip()
                or type(text) is not str
                or not text.strip()
            ):
                raise KnowledgeBaseError(
                    f"Rule {rule_id!r} recommendation fields must be nonempty strings."
                )
            recommendations.append({"action": action, "reason": text})
        if expose_finding:
            if conclusion.get("pause_robot") is not True:
                raise KnowledgeBaseError(
                    f"Finding rule {rule_id!r} must set conclusion.pause_robot to true."
                )
            if not recommendations or not any(
                item["action"] == "pause_robot" for item in recommendations
            ):
                raise KnowledgeBaseError(
                    f"Finding rule {rule_id!r} must recommend pause_robot for the simulation."
                )
        elif recommendations:
            raise KnowledgeBaseError(
                f"Intermediate rule {rule_id!r} cannot publish recommendations."
            )
        elif conclusion.get("pause_robot") is True:
            raise KnowledgeBaseError(
                f"Non-finding rule {rule_id!r} cannot set conclusion.pause_robot to true."
            )

        parsed_rules.append(
            Rule(
                id=rule_id,
                validation="illustrative",
                premises=copy.deepcopy(premises),
                conclusion=copy.deepcopy(conclusion),
                reason=reason,
                expose_finding=expose_finding,
                recommendations=tuple(recommendations),
            )
        )

    derived_names = set(derived_values)
    if not derived_names:
        raise KnowledgeBaseError("Knowledge base must declare at least one derived fact.")
    for rule in parsed_rules:
        for name, expected in rule.premises.items():
            if type(name) is not str or not name.strip():
                raise KnowledgeBaseError(f"Rule {rule.id!r} premise names must be strings.")
            if name in observations:
                spec = observations[name]
                if not _matches_type(expected, spec["type"]) or not any(
                    _typed_equal(expected, allowed)
                    for allowed in spec["allowed_values"]
                ):
                    raise KnowledgeBaseError(
                        f"Rule {rule.id!r} premise for raw observation {name!r} "
                        "is not one of its declared allowed values."
                    )
            elif name in derived_values:
                if not _typed_equal(expected, derived_values[name]):
                    raise KnowledgeBaseError(
                        f"Rule {rule.id!r} premise for derived fact {name!r} "
                        "does not match its declared conclusion value."
                    )
            else:
                raise KnowledgeBaseError(
                    f"Rule {rule.id!r} refers to undeclared fact {name!r}."
                )

    ungrouped = set(observations) - required_set - grouped_observations
    if ungrouped:
        raise KnowledgeBaseError(
            "Every optional observation must belong to exactly one diagnostic group; "
            f"unclassified observations: {sorted(ungrouped)}."
        )

    return KnowledgeBase(
        provenance=provenance,
        observations=observations,
        required_observations=required,
        groups=tuple(groups),
        rules=tuple(parsed_rules),
        document=document,
        schema_version=document["schema_version"],
    )


_MISSING = object()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _read_json_with_hash(path: Path) -> tuple[Any, str]:
    try:
        content = path.read_bytes()
        text = content.decode("utf-8")
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_unique_object_pairs,
        )
        return payload, hashlib.sha256(content).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise KnowledgeBaseError(f"Could not load JSON from {path}: {error}") from error


def _read_json(path: Path) -> Any:
    return _read_json_with_hash(path)[0]


def load_knowledge_base(path: str | Path | None = None) -> KnowledgeBase:
    """Read and validate the default or a caller-provided knowledge-base JSON file."""
    source = Path(path) if path is not None else _KB_PATH
    payload, source_sha256 = _read_json_with_hash(source)
    try:
        knowledge_base = validate_knowledge_base(payload)
        return KnowledgeBase(
            provenance=knowledge_base.provenance,
            observations=knowledge_base.observations,
            required_observations=knowledge_base.required_observations,
            groups=knowledge_base.groups,
            rules=knowledge_base.rules,
            document=knowledge_base.document,
            schema_version=knowledge_base.schema_version,
            source_path=str(source.resolve()),
            source_sha256=source_sha256,
        )
    except KnowledgeBaseError as error:
        raise KnowledgeBaseError(f"Invalid knowledge base {source}: {error}") from error


def get_observation_schema() -> dict[str, Any]:
    """Return the validated raw observation and optional-group schema for clients."""
    knowledge_base = load_knowledge_base()
    return {
        "required_observations": list(knowledge_base.required_observations),
        "observations": {
            name: {
                "type": spec["type"],
                "allowed_values": list(spec["allowed_values"]),
            }
            for name, spec in knowledge_base.observations.items()
        },
        "groups": [
            {"id": group.id, "observations": list(group.observations)}
            for group in knowledge_base.groups
        ],
    }


def knowledge_base_metadata(knowledge_base: KnowledgeBase) -> dict[str, Any]:
    """Return stable source details suitable for CLI evidence records."""
    source_label: str | None = None
    if knowledge_base.source_path is not None:
        source_path = Path(knowledge_base.source_path).resolve()
        project_root = Path(__file__).resolve().parents[1]
        try:
            source_label = source_path.relative_to(project_root).as_posix()
        except ValueError:
            source_label = f"external/{source_path.name}"
    return {
        "source": source_label,
        "sha256": knowledge_base.source_sha256,
        "schema_version": knowledge_base.schema_version,
        "provenance": knowledge_base.provenance,
    }


def _validate_facts(facts: Any, knowledge_base: KnowledgeBase) -> bool:
    if type(facts) is not dict:
        return False
    for name, value in facts.items():
        if type(name) is not str or name not in knowledge_base.observations:
            return False
        if value is None:
            continue
        spec = knowledge_base.observations[name]
        if not _matches_type(value, spec["type"]) or not any(
            _typed_equal(value, allowed)
            for allowed in spec["allowed_values"]
        ):
            return False
    return True


def _missing_facts(facts: dict[str, Any], knowledge_base: KnowledgeBase) -> list[str]:
    missing = [
        name
        for name in knowledge_base.required_observations
        if name not in facts or facts[name] is None
    ]
    for group in knowledge_base.groups:
        # Optional evidence stays optional until the caller supplies at least one
        # known member of that diagnostic group.
        if not any(facts.get(name) is not None for name in group.observations):
            continue
        missing.extend(
            name
            for name in group.observations
            if name not in facts or facts[name] is None
        )
    return missing


def infer(facts: dict[str, Any], knowledge_base: KnowledgeBase | dict[str, Any]) -> dict[str, Any]:
    """Infer from raw observations using a validated or fixture knowledge base.

    This public entry point makes custom JSON rule fixtures easy to exercise:
    call ``validate_knowledge_base(payload)`` and pass its result here. Passing
    a raw fixture dictionary is also supported and validates it on the spot.
    """
    if isinstance(knowledge_base, KnowledgeBase):
        # Revalidate an isolated copy so fixture callers cannot mutate a loaded
        # nested dictionary into inconsistent rules after validation.
        knowledge_base = validate_knowledge_base(knowledge_base.as_dict())
    else:
        knowledge_base = validate_knowledge_base(knowledge_base)

    result = _empty_result("ok")
    if not _validate_facts(facts, knowledge_base):
        result["status"] = "invalid_input"
        return result

    result["missing_facts"] = _missing_facts(facts, knowledge_base)
    if result["missing_facts"]:
        result["status"] = "insufficient_evidence"

    known_facts = {
        name: value for name, value in facts.items() if value is not None
    }
    # Each derived fact stores the first deterministic grounded proof. Keeping
    # that proof stable prevents cyclic rules from recursively growing ancestry.
    derived_proofs: dict[str, list[str]] = {}
    fired_rule_ids: set[str] = set()
    trace: list[dict[str, Any]] = []
    findings_by_condition: dict[str, list[str]] = {}
    recommendation_keys: set[tuple[str, str]] = set()

    while True:
        new_fact_derived = False
        for rule in knowledge_base.rules:
            if rule.id in fired_rule_ids:
                continue
            if not all(
                name in known_facts and _typed_equal(known_facts[name], expected)
                for name, expected in rule.premises.items()
            ):
                continue

            condition = rule.conclusion["condition"]
            value = rule.derived_value
            if condition in known_facts and not _typed_equal(known_facts[condition], value):
                # Loader validation normally makes this unreachable. Keep the
                # guard at inference time for custom or concurrently modified data.
                raise KnowledgeBaseError(
                    f"Rule {rule.id!r} conflicts with the known value of {condition!r}."
                )

            supporting_ids: list[str] = []
            for premise_name in rule.premises:
                supporting_ids.extend(derived_proofs.get(premise_name, []))
            proof_ids = list(dict.fromkeys([*supporting_ids, rule.id]))
            trace.append(
                {
                    "rule_id": rule.id,
                    "premises": copy.deepcopy(rule.premises),
                    "conclusion": copy.deepcopy(rule.conclusion),
                    "reason": rule.reason,
                }
            )
            fired_rule_ids.add(rule.id)

            if condition not in known_facts:
                known_facts[condition] = copy.deepcopy(value)
                derived_proofs[condition] = proof_ids
                new_fact_derived = True

            if rule.expose_finding:
                ids = findings_by_condition.setdefault(condition, [])
                ids.extend(rule_id for rule_id in proof_ids if rule_id not in ids)
                for recommendation in rule.recommendations:
                    key = (recommendation["action"], recommendation["reason"])
                    if key not in recommendation_keys:
                        recommendation_keys.add(key)
                        result["recommendations"].append(
                            copy.deepcopy(recommendation)
                        )
        if not new_fact_derived:
            break

    result["findings"] = [
        {"condition": condition, "rule_ids": rule_ids}
        for condition, rule_ids in findings_by_condition.items()
    ]
    result["rule_trace"] = trace
    return result


def diagnose(facts: dict[str, object]) -> dict[str, Any]:
    """Return a fresh diagnosis with the exact agreed JSON fields.

    Missing and ``None`` observations are unknown, never false. Unsupported raw
    observations return ``invalid_input``. Knowledge-base problems raise
    :class:`KnowledgeBaseError` so the application adapter can report a broken
    diagnostic module rather than mislabeling a user's observations.
    """
    knowledge_base = load_knowledge_base()
    return infer(facts, knowledge_base)
