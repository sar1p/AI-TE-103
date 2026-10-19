"""Adaptive Neuro-Fuzzy Inference System (ANFIS) for warehouse robot analytics.

Implements a first-order Takagi-Sugeno neuro-fuzzy inference model:
- Layer 1: Gaussian fuzzification with adaptive premise parameters (mean, sigma).
- Layer 2: Rule firing strength via T-norm (product).
- Layer 3: Normalized firing strengths.
- Layer 4: Linear consequent equations (p_i * x + r_i).
- Layer 5: Defuzzified continuous output.
- Gradient descent backpropagation for premise and consequent parameter tuning.
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Any


class ANFISError(ValueError):
    """Raised when ANFIS inputs or configurations are invalid."""


def _gaussian_mf(x: float, c: float, sigma: float) -> float:
    safe_sigma = max(1e-5, abs(sigma))
    diff = (x - c) / safe_sigma
    return math.exp(-0.5 * (diff ** 2))


@dataclass
class RuleParameters:
    # Premise Gaussian centers and sigmas for each input feature
    centers: list[float]
    sigmas: list[float]
    # Consequent linear weights: [p_0, p_1, ..., r]
    consequent: list[float]


class ANFIS:
    """Adaptive Neuro-Fuzzy Inference System with Takagi-Sugeno rules."""

    def __init__(
        self,
        n_inputs: int = 2,
        mfs_per_input: int = 2,
        seed: int = 42,
    ) -> None:
        if n_inputs <= 0 or not isinstance(n_inputs, int):
            raise ANFISError("n_inputs must be a positive integer")
        if mfs_per_input < 2 or not isinstance(mfs_per_input, int):
            raise ANFISError("mfs_per_input must be >= 2")

        self.n_inputs = n_inputs
        self.mfs_per_input = mfs_per_input
        self.rng = random.Random(seed)

        # Number of rules: mfs_per_input ^ n_inputs
        self.n_rules = mfs_per_input ** n_inputs
        self.rules: list[RuleParameters] = []
        self._init_parameters()

    def _init_parameters(self) -> None:
        """Initialize membership functions and consequent weights evenly."""
        mf_centers_per_dim = []
        for _ in range(self.n_inputs):
            # Default centers spaced between 0.0 and 1.0
            step = 1.0 / max(1, self.mfs_per_input - 1)
            centers = [i * step for i in range(self.mfs_per_input)]
            mf_centers_per_dim.append(centers)

        combos = list(itertools.product(*mf_centers_per_dim))
        self.rules = []

        for combo in combos:
            centers = list(combo)
            sigmas = [0.35] * self.n_inputs
            # Consequent weights initialized randomly around 0
            consequent = [self.rng.uniform(-0.1, 0.1) for _ in range(self.n_inputs + 1)]
            self.rules.append(RuleParameters(centers=centers, sigmas=sigmas, consequent=consequent))

    def _forward_sample(
        self, x: list[float]
    ) -> tuple[float, list[float], list[float], list[float]]:
        """Compute layers 1 to 5 for a single sample x.

        Returns:
            y_pred: final scalar prediction
            w: raw firing strengths
            w_bar: normalized firing strengths
            f: consequent outputs per rule
        """
        w = []
        for rule in self.rules:
            strength = 1.0
            for j in range(self.n_inputs):
                strength *= _gaussian_mf(x[j], rule.centers[j], rule.sigmas[j])
            w.append(strength)

        total_w = sum(w)
        if total_w < 1e-9:
            w_bar = [1.0 / self.n_rules] * self.n_rules
        else:
            w_bar = [val / total_w for val in w]

        f = []
        for rule in self.rules:
            # f_i = p_0 * x_0 + ... + p_{n-1} * x_{n-1} + r
            rule_out = sum(rule.consequent[j] * x[j] for j in range(self.n_inputs)) + rule.consequent[-1]
            f.append(rule_out)

        y_pred = sum(w_bar[i] * f[i] for i in range(self.n_rules))
        return y_pred, w, w_bar, f

    def predict_one(self, x: list[float] | tuple[float, ...]) -> float:
        """Predict target value for a single feature vector."""
        if len(x) != self.n_inputs:
            raise ANFISError(f"Expected {self.n_inputs} features, got {len(x)}")
        y_pred, _, _, _ = self._forward_sample(list(x))
        return float(y_pred)

    def predict(self, X: list[list[float]] | list[tuple[float, ...]]) -> list[float]:
        """Predict target values for multiple samples."""
        return [self.predict_one(row) for row in X]

    def fit(
        self,
        X: list[list[float]],
        y: list[float],
        epochs: int = 100,
        learning_rate: float = 0.02,
    ) -> list[float]:
        """Train ANFIS parameters using gradient descent backpropagation."""
        if not X or not y or len(X) != len(y):
            raise ANFISError("X and y must be nonempty lists with matching lengths")
        if epochs <= 0:
            raise ANFISError("epochs must be positive")
        if learning_rate <= 0:
            raise ANFISError("learning_rate must be positive")

        n_samples = len(X)
        loss_history: list[float] = []

        for epoch in range(epochs):
            total_loss = 0.0

            for sample_idx in range(n_samples):
                x_sample = X[sample_idx]
                y_true = y[sample_idx]

                y_pred, w, w_bar, f = self._forward_sample(x_sample)
                error = y_pred - y_true
                total_loss += error ** 2

                total_w = sum(w)
                safe_total_w = max(1e-9, total_w)

                # Gradient updates for each rule
                for i, rule in enumerate(self.rules):
                    # 1. Consequent parameters update (dL / dp_j, dL / dr)
                    # dL/dp_j = error * w_bar_i * x_j
                    for j in range(self.n_inputs):
                        grad_p = error * w_bar[i] * x_sample[j]
                        rule.consequent[j] -= learning_rate * grad_p
                    # dL/dr = error * w_bar_i
                    grad_r = error * w_bar[i]
                    rule.consequent[-1] -= learning_rate * grad_r

                    # 2. Premise parameters update (dL / dc_j, dL / dsigma_j)
                    # dL/d(w_bar_i) = error * f_i
                    # d(w_bar_i)/d(w_i) = (sum_w - w_i) / (sum_w ^ 2)
                    d_wbar_d_wi = (safe_total_w - w[i]) / (safe_total_w ** 2)
                    d_loss_d_wi = error * (f[i] - y_pred) * d_wbar_d_wi

                    for j in range(self.n_inputs):
                        diff = x_sample[j] - rule.centers[j]
                        safe_sig = max(1e-5, abs(rule.sigmas[j]))

                        # d(w_i)/d(c_j) = w_i * diff / (sigma_j ^ 2)
                        grad_c = d_loss_d_wi * (w[i] * diff / (safe_sig ** 2))
                        # d(w_i)/d(sigma_j) = w_i * (diff ^ 2) / (sigma_j ^ 3)
                        grad_sig = d_loss_d_wi * (w[i] * (diff ** 2) / (safe_sig ** 3))

                        # Clip gradients for numerical stability
                        grad_c = max(-5.0, min(5.0, grad_c))
                        grad_sig = max(-5.0, min(5.0, grad_sig))

                        rule.centers[j] -= learning_rate * grad_c
                        rule.sigmas[j] = max(0.05, rule.sigmas[j] - learning_rate * grad_sig)

            mse = total_loss / n_samples
            loss_history.append(mse)

        return loss_history

    def evaluate(self, X: list[list[float]], y: list[float]) -> dict[str, float]:
        """Compute regression evaluation metrics (MSE, RMSE, MAE)."""
        if len(X) != len(y) or not X:
            raise ANFISError("X and y must be nonempty lists with matching lengths")
        preds = self.predict(X)
        errors = [p - t for p, t in zip(preds, y)]
        mse = sum(e ** 2 for e in errors) / len(errors)
        rmse = math.sqrt(mse)
        mae = sum(abs(e) for e in errors) / len(errors)
        return {
            "mse": round(mse, 6),
            "rmse": round(rmse, 6),
            "mae": round(mae, 6),
        }

    def to_dict(self) -> dict[str, Any]:
        """Export rule parameters for diagnostics and reporting."""
        return {
            "n_inputs": self.n_inputs,
            "mfs_per_input": self.mfs_per_input,
            "n_rules": self.n_rules,
            "rules": [
                {
                    "rule_id": idx,
                    "centers": [round(c, 4) for c in r.centers],
                    "sigmas": [round(s, 4) for s in r.sigmas],
                    "consequent": [round(w, 4) for w in r.consequent],
                }
                for idx, r in enumerate(self.rules)
            ],
        }


def generate_warehouse_training_data(
    n_samples: int = 120, seed: int = 42
) -> tuple[list[list[float]], list[float]]:
    """Synthesize realistic warehouse data for robot travel time / distance estimation.

    Inputs:
      - x0: normalized distance / planned path length [0.0 - 1.0]
      - x1: obstacle density / clutter ratio [0.0 - 1.0]
    Output:
      - y: actual traversal time (units), accounting for slowdown near clutter
    """
    rng = random.Random(seed)
    X: list[list[float]] = []
    y: list[float] = []

    for _ in range(n_samples):
        distance = rng.uniform(0.1, 0.95)
        clutter = rng.uniform(0.05, 0.90)

        # Realistic non-linear model: time increases with distance and extra congestion delay
        traversal_time = 1.2 * distance + 0.8 * clutter + 0.5 * (distance * clutter) + rng.gauss(0.0, 0.02)
        X.append([round(distance, 4), round(clutter, 4)])
        y.append(round(traversal_time, 4))

    return X, y
