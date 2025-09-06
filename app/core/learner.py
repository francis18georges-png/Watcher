"""Persistent benchmark-based learner for simple self-improvement."""

from __future__ import annotations

from pathlib import Path
import json

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

    def step(self, state: list[float], reward: float) -> list[float]:
        """Update policy parameters based on ``reward`` and previous state.

        The update implements a minimal REINFORCE gradient: ``grad = reward *
        prev_state``.  The *current* ``state`` is stored for the next
        invocation.
        """

        if not self.params:
            # Lazy initialisation matching state dimensionality
            self.params = [0.0 for _ in state]

        if self.prev_state is not None:
            grad = [reward * s for s in self.prev_state]
            self.params = [p + self.lr * g for p, g in zip(self.params, grad)]

        self.prev_state = state
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
