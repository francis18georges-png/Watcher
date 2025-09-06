"""Persistent learner with a tiny reinforcement policy.

This module persists benchmark results and maintains a very small policy used
to pick between prompt variants.  After every training iteration the learner
receives a reward signal allowing it to favour prompts that historically led
to higher quality outputs.
"""

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

    def update_policy(self, reward: float, context: dict | None = None) -> str:
        """Update the internal policy using a simple reinforcement rule.

        Args:
            reward: Feedback signal in ``[−inf, +inf]``.  Positive values
                encourage the variant used in ``context``.
            context: Optional metadata such as ``{"prompt": "A"}`` indicating
                which variant produced the reward.

        Returns:
            The name of the currently preferred prompt variant.
        """

        policy = self._load_policy()
        ctx = context or {}
        variant = (
            ctx.get("prompt") or ctx.get("variant") or policy.get("current_prompt", "A")
        )

        stats = policy.setdefault("stats", {})
        stat = stats.setdefault(variant, {"reward": 0.0, "count": 0})
        stat["reward"] += float(reward)
        stat["count"] += 1

        # Choose variant with highest average reward
        best = max(
            stats.items(),
            key=lambda kv: kv[1]["reward"] / max(1, kv[1]["count"]),
        )[0]
        policy["current_prompt"] = best
        self._save_policy(policy)
        return best

    def _load_best(self) -> dict | None:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _save_best(self, best: dict) -> None:
        self.file.write_text(json.dumps(best), encoding="utf-8")

    def _load_policy(self) -> dict:
        if self.policy_file.exists():
            try:
                return json.loads(self.policy_file.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                pass
        return {"current_prompt": "A", "stats": {}}

    def _save_policy(self, policy: dict) -> None:
        self.policy_file.write_text(json.dumps(policy), encoding="utf-8")
