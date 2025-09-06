"""Persistent benchmark-based learner for simple self-improvement."""

from __future__ import annotations

from pathlib import Path
import json
import math

from typing import Any

from app.core.benchmark import Bench


class Learner:
    """Track benchmark results, remember best variant and learn from context."""

    def __init__(self, bench: Bench, data_dir: Path) -> None:
        self.bench = bench
        self.file = data_dir / "best_variant.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)

        # Simple policy parameters and learning state for REINFORCE-style updates
        self.params: list[float] = []
        self.prev_state: list[float] | None = None
        self.lr = 0.1

        # Adam optimiser state
        self.m: list[float] = []
        self.v: list[float] = []
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.eps = 1e-8
        self.t = 0

        # Persist policy parameters between runs so training can resume
        self.params_path = data_dir / "policy_params.json"
        if self.params_path.exists():
            try:
                obj = json.loads(self.params_path.read_text(encoding="utf-8"))
                self.params = list(obj.get("params", []))
                # Ensure optimiser state matches parameter dimensionality
                self.m = [0.0 for _ in self.params]
                self.v = [0.0 for _ in self.params]
            except Exception:  # pragma: no cover - defensive
                pass

    def step(self, state: list[float], reward: float) -> list[float]:
        """Update policy parameters based on ``reward`` and previous state.

        The update implements a minimal REINFORCE gradient: ``grad = reward *
        prev_state``.  The *current* ``state`` is stored for the next
        invocation.
        """

        if not self.params:
            # Lazy initialisation matching state dimensionality
            self.params = [0.0 for _ in state]
            self.m = [0.0 for _ in state]
            self.v = [0.0 for _ in state]

        if self.prev_state is not None:
            # Normalise state to stabilise updates
            mean = sum(self.prev_state) / len(self.prev_state)
            std = math.sqrt(
                sum((s - mean) ** 2 for s in self.prev_state) / len(self.prev_state)
            ) or 1.0
            norm_prev = [(s - mean) / std for s in self.prev_state]

            grad = [reward * s for s in norm_prev]
            # Gradient clipping
            grad = [max(min(g, 1.0), -1.0) for g in grad]

            # Adam update
            self.t += 1
            self.m = [
                self.beta1 * m + (1 - self.beta1) * g for m, g in zip(self.m, grad)
            ]
            self.v = [
                self.beta2 * v + (1 - self.beta2) * (g ** 2)
                for v, g in zip(self.v, grad)
            ]
            m_hat = [m / (1 - self.beta1**self.t) for m in self.m]
            v_hat = [v / (1 - self.beta2**self.t) for v in self.v]
            self.params = [
                p + self.lr * m / (math.sqrt(v) + self.eps)
                for p, m, v in zip(self.params, m_hat, v_hat)
            ]
            self._save_params()

        # Store normalised current state for next call
        mean = sum(state) / len(state) if state else 0.0
        std = math.sqrt(sum((s - mean) ** 2 for s in state) / len(state)) or 1.0
        self.prev_state = [(s - mean) / std for s in state]
        return self.params

    def compare(self, a: str, b: str) -> dict:
        """Benchmark two variants and persist the best result."""
        score_a = self.bench.run_variant(a)
        score_b = self.bench.run_variant(b)
        name, score = (a, score_a) if score_a >= score_b else (b, score_b)
        best = self._load_best()
        if not best or score > best.get("score", -1.0):
            best = {"name": name, "score": score}
            self._save_best(best)
        return {"A": score_a, "B": score_b, "best": best}

    def _load_best(self) -> dict | None:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _save_best(self, best: dict) -> None:
        self.file.write_text(json.dumps(best), encoding="utf-8")

    def _save_params(self) -> None:
        try:
            data: dict[str, Any] = {"params": self.params}
            self.params_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception:  # pragma: no cover - defensive
            pass
