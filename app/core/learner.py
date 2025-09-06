"""Persistent benchmark-based learner for simple self-improvement."""

from __future__ import annotations

from pathlib import Path
import json

from app.core.benchmark import Bench


class Learner:
    """Track benchmark results and remember the best variant."""

    def __init__(self, bench: Bench, data_dir: Path) -> None:
        self.bench = bench
        self.file = data_dir / "best_variant.json"
        self.policy_file = data_dir / "policy.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)

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

    def update_policy(self, reward: float) -> None:
        """Update the learning policy based on a reward signal.

        The current policy is a simple log of the latest reward value,
        persisted to ``policy.json`` for potential future use.
        """
        self.policy_file.write_text(
            json.dumps({"last_reward": reward}), encoding="utf-8"
        )

    def _load_best(self) -> dict | None:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _save_best(self, best: dict) -> None:
        self.file.write_text(json.dumps(best), encoding="utf-8")
