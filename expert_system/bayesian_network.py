"""Discrete Bayesian Network with exact inference for probabilistic robot diagnostics.

Models causal dependencies between warehouse robot faults and sensor observations:
- Nodes represent discrete random variables (e.g., motor overheating, sensor readings).
- Conditional Probability Tables (CPTs) define priors and conditional distributions.
- Exact inference via enumeration / variable elimination computes posterior distributions
  given evidence: P(Fault | Evidence).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any


class BayesianNetworkError(ValueError):
    """Raised when network structure, CPT, or query is invalid."""


@dataclass
class DiscreteVariable:
    name: str
    states: tuple[str, ...]
    parents: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise BayesianNetworkError("Variable name must be a nonempty string")
        if not self.states or len(self.states) < 2:
            raise BayesianNetworkError(f"Variable '{self.name}' must have at least 2 discrete states")
        if len(set(self.states)) != len(self.states):
            raise BayesianNetworkError(f"Duplicate states in variable '{self.name}'")


class BayesianNetwork:
    """Discrete Bayesian Network supporting exact inference with evidence."""

    def __init__(self) -> None:
        self.variables: dict[str, DiscreteVariable] = {}
        # CPT maps variable name -> dict of parent_assignment_tuple -> dict of state -> probability
        # For root nodes (no parents), parent_assignment is an empty tuple ()
        self.cpt: dict[str, dict[tuple[tuple[str, str], ...], dict[str, float]]] = {}

    def add_variable(
        self,
        name: str,
        states: tuple[str, ...] | list[str],
        parents: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Add a discrete variable to the Bayesian Network."""
        if name in self.variables:
            raise BayesianNetworkError(f"Variable '{name}' already exists in network")
        parent_tuple = tuple(parents)
        for p in parent_tuple:
            if p not in self.variables:
                raise BayesianNetworkError(f"Parent variable '{p}' must be added before child '{name}'")

        var = DiscreteVariable(name=name, states=tuple(states), parents=parent_tuple)
        self.variables[name] = var
        self.cpt[name] = {}
        self._validate_dag()

    def _validate_dag(self) -> None:
        """Ensure network has no directed cycles (DAG check)."""
        visited: dict[str, int] = {}  # 0: visiting, 1: visited

        def visit(node: str) -> None:
            if visited.get(node) == 0:
                raise BayesianNetworkError(f"Cycle detected involving variable '{node}'")
            if visited.get(node) == 1:
                return
            visited[node] = 0
            for child, var in self.variables.items():
                if node in var.parents:
                    visit(child)
            visited[node] = 1

        for v in self.variables:
            if v not in visited:
                visit(v)

    def set_cpt(
        self,
        variable: str,
        table: dict[Any, dict[str, float]],
    ) -> None:
        """Assign conditional probability table for a variable.

        table:
          - If no parents: {"true": 0.05, "false": 0.95}
          - If has parents: {
                (("parent1", "val1"), ("parent2", "val2")): {"true": 0.8, "false": 0.2},
                ...
            }
        """
        if variable not in self.variables:
            raise BayesianNetworkError(f"Variable '{variable}' does not exist")

        var = self.variables[variable]
        normalized_cpt: dict[tuple[tuple[str, str], ...], dict[str, float]] = {}

        if not var.parents:
            # Root variable
            if not isinstance(table, dict):
                raise BayesianNetworkError(f"CPT for root '{variable}' must be a state->prob dict")
            self._validate_distribution(var, table)
            normalized_cpt[()] = {k: float(v) for k, v in table.items()}
        else:
            # Generate expected combinations of parent assignments
            parent_states = [self.variables[p].states for p in var.parents]
            expected_combos = list(itertools.product(*parent_states))

            for combo in expected_combos:
                key = tuple((var.parents[i], combo[i]) for i in range(len(var.parents)))
                # Support matching either exact key or dict key
                dist = None
                if key in table:
                    dist = table[key]
                else:
                    # Try matching simple tuple of values or dict
                    for k, v in table.items():
                        if isinstance(k, tuple):
                            if k == combo or k == key:
                                dist = v
                                break
                        elif isinstance(k, dict):
                            if all(k.get(p) == combo[i] for i, p in enumerate(var.parents)):
                                dist = v
                                break

                if dist is None:
                    raise BayesianNetworkError(
                        f"Missing CPT entry for variable '{variable}' with parents {key}"
                    )
                self._validate_distribution(var, dist)
                normalized_cpt[key] = {s: float(dist[s]) for s in var.states}

        self.cpt[variable] = normalized_cpt

    def _validate_distribution(self, var: DiscreteVariable, dist: dict[str, float]) -> None:
        for s in var.states:
            if s not in dist:
                raise BayesianNetworkError(f"Missing state '{s}' in CPT for '{var.name}'")
            val = dist[s]
            if not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0.0 or val > 1.0:
                raise BayesianNetworkError(f"Invalid probability {val} for state '{s}' in '{var.name}'")
        total = sum(dist[s] for s in var.states)
        if abs(total - 1.0) > 1e-4:
            raise BayesianNetworkError(
                f"Probabilities for variable '{var.name}' must sum to 1.0 (got {total})"
            )

    def _probability(self, variable: str, state: str, full_assignment: dict[str, str]) -> float:
        var = self.variables[variable]
        if not var.parents:
            return self.cpt[variable][()][state]
        parent_key = tuple((p, full_assignment[p]) for p in var.parents)
        return self.cpt[variable][parent_key][state]

    def joint_probability(self, assignment: dict[str, str]) -> float:
        """Compute the joint probability P(X1=x1, X2=x2, ...) for all variables."""
        if set(assignment.keys()) != set(self.variables.keys()):
            raise BayesianNetworkError("Joint probability requires assignment for all variables")
        prob = 1.0
        for var_name, state in assignment.items():
            prob *= self._probability(var_name, state, assignment)
        return prob

    def query(
        self,
        target: str,
        evidence: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """Compute posterior distribution P(Target | Evidence) using exact inference."""
        if target not in self.variables:
            raise BayesianNetworkError(f"Target variable '{target}' not found in network")

        evidence = evidence or {}
        for ev_var, ev_val in evidence.items():
            if ev_var not in self.variables:
                raise BayesianNetworkError(f"Evidence variable '{ev_var}' not found in network")
            if ev_val not in self.variables[ev_var].states:
                raise BayesianNetworkError(
                    f"State '{ev_val}' is invalid for evidence variable '{ev_var}'"
                )

        target_var = self.variables[target]
        if target in evidence:
            return {s: (1.0 if s == evidence[target] else 0.0) for s in target_var.states}

        hidden_vars = [v for v in self.variables if v != target and v not in evidence]
        unnormalized: dict[str, float] = {}

        for state in target_var.states:
            assignment = dict(evidence)
            assignment[target] = state

            # Sum over all configurations of hidden variables
            total_prob = 0.0
            if not hidden_vars:
                total_prob = self.joint_probability(assignment)
            else:
                hidden_states = [self.variables[h].states for h in hidden_vars]
                for combo in itertools.product(*hidden_states):
                    full_assign = dict(assignment)
                    for i, h in enumerate(hidden_vars):
                        full_assign[h] = combo[i]
                    total_prob += self.joint_probability(full_assign)

            unnormalized[state] = total_prob

        total_sum = sum(unnormalized.values())
        if total_sum <= 0.0:
            # Contradictory evidence or zero probability
            raise BayesianNetworkError("Inconsistent or impossible evidence (P(Evidence) = 0)")

        return {s: round(unnormalized[s] / total_sum, 6) for s in target_var.states}

    def diagnose_all_faults(
        self,
        fault_variables: list[str],
        evidence: dict[str, str],
    ) -> dict[str, dict[str, float]]:
        """Compute posterior probabilities for multiple fault targets given observed evidence."""
        results: dict[str, dict[str, float]] = {}
        for fault in fault_variables:
            results[fault] = self.query(fault, evidence)
        return results

    def to_dict(self) -> dict[str, Any]:
        """Export network architecture for inspection and diagnostics evidence."""
        return {
            "variables": {
                name: {"states": list(var.states), "parents": list(var.parents)}
                for name, var in self.variables.items()
            },
            "variable_count": len(self.variables),
        }


def get_default_warehouse_bayesian_network() -> BayesianNetwork:
    """Preconfigured Bayesian Network for warehouse robot diagnostics.

    Variables:
    - MotorOverheat (True, False)
    - BatteryFault (True, False)
    - DriveTrainFault (True, False)
    - MotorTemperature (normal, high)
    - CurrentDraw (normal, high)
    - VoltageDrop (normal, high)
    - Vibration (low, high)
    """
    bn = BayesianNetwork()

    # 1. Fault root variables
    bn.add_variable("MotorOverheat", states=["false", "true"])
    bn.add_variable("BatteryFault", states=["false", "true"])
    bn.add_variable("DriveTrainFault", states=["false", "true"])

    # Priors
    bn.set_cpt("MotorOverheat", {"false": 0.92, "true": 0.08})
    bn.set_cpt("BatteryFault", {"false": 0.95, "true": 0.05})
    bn.set_cpt("DriveTrainFault", {"false": 0.90, "true": 0.10})

    # 2. Sensor observations depending on faults
    # MotorTemperature depends on MotorOverheat
    bn.add_variable("MotorTemperature", states=["normal", "high"], parents=["MotorOverheat"])
    bn.set_cpt("MotorTemperature", {
        (("MotorOverheat", "false"),): {"normal": 0.95, "high": 0.05},
        (("MotorOverheat", "true"),): {"normal": 0.10, "high": 0.90},
    })

    # CurrentDraw depends on MotorOverheat and DriveTrainFault
    bn.add_variable("CurrentDraw", states=["normal", "high"], parents=["MotorOverheat", "DriveTrainFault"])
    bn.set_cpt("CurrentDraw", {
        (("MotorOverheat", "false"), ("DriveTrainFault", "false")): {"normal": 0.94, "high": 0.06},
        (("MotorOverheat", "false"), ("DriveTrainFault", "true")): {"normal": 0.25, "high": 0.75},
        (("MotorOverheat", "true"), ("DriveTrainFault", "false")): {"normal": 0.30, "high": 0.70},
        (("MotorOverheat", "true"), ("DriveTrainFault", "true")): {"normal": 0.05, "high": 0.95},
    })

    # VoltageDrop depends on BatteryFault
    bn.add_variable("VoltageDrop", states=["normal", "high"], parents=["BatteryFault"])
    bn.set_cpt("VoltageDrop", {
        (("BatteryFault", "false"),): {"normal": 0.96, "high": 0.04},
        (("BatteryFault", "true"),): {"normal": 0.15, "high": 0.85},
    })

    # Vibration depends on DriveTrainFault
    bn.add_variable("Vibration", states=["low", "high"], parents=["DriveTrainFault"])
    bn.set_cpt("Vibration", {
        (("DriveTrainFault", "false"),): {"low": 0.92, "high": 0.08},
        (("DriveTrainFault", "true"),): {"low": 0.20, "high": 0.80},
    })

    return bn
