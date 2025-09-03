"""Persistent benchmark-based learner for simple self-improvement."""
from __future__ import annotations

from pathlib import Path
import json
import time

from app.core.benchmark import Bench


class Learner:
    """Track benchmark results and remember the best variant.

    The learner persists the best-performing variant and keeps a history of all
    benchmark comparisons to enable basic long-term self-improvement.
    """

    def __init__(self, bench: Bench, data_dir: Path) -> None:
        self.bench = bench
        self.data_dir = data_dir
        self.file = data_dir / "best_variant.json"
        self.history_file = data_dir / "history.jsonl"
        self.counter_file = data_dir / "variant_counter.txt"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Variant management
    # ------------------------------------------------------------------
    def current_best(self) -> str:
        """Return the currently best known variant name."""
        best = self._load_best()
        return best["name"] if best else "base"

    def suggest(self) -> str:
        """Suggest a new variant name derived from the current best."""
        base = self.current_best()
        n = self._next_counter()
        return f"{base}_{n}"

    def _next_counter(self) -> int:
        n = 0
        if self.counter_file.exists():
            try:
                n = int(self.counter_file.read_text())
            except Exception:  # pragma: no cover - defensive
                n = 0
        n += 1
        self.counter_file.write_text(str(n))
        return n

    # ------------------------------------------------------------------
    # Benchmarking
    # ------------------------------------------------------------------
    def compare(self, a: str, b: str) -> dict:
        """Benchmark two variants, persist the best result and log history."""
        score_a = self.bench.run_variant(a)
        score_b = self.bench.run_variant(b)
        name, score = (a, score_a) if score_a >= score_b else (b, score_b)
        best = self._load_best()
        if not best or score > best.get("score", -1.0):
            best = {"name": name, "score": score}
            self._save_best(best)
        self._append_history(a, score_a, b, score_b, best)
        return {"A": score_a, "B": score_b, "best": best}

    def optimize(self, iterations: int = 3) -> dict:
        """Run successive comparisons to seek better variants.

        The learner will repeatedly benchmark the current best variant against a
        newly suggested one. After *iterations* rounds, the result of the final
        comparison is returned and the best variant is persisted.
        """

        last: dict = {}
        for _ in range(iterations):
            base = self.current_best()
            cand = self.suggest()
            last = self.compare(base, cand)
        last["iterations"] = iterations
        return last

    def _append_history(
        self, a: str, score_a: float, b: str, score_b: float, best: dict
    ) -> None:
        rec = {
            "ts": time.time(),
            "a": {"name": a, "score": score_a},
            "b": {"name": b, "score": score_b},
            "best": best,
        }
        with self.history_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def _load_best(self) -> dict | None:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _save_best(self, best: dict) -> None:
        self.file.write_text(json.dumps(best), encoding="utf-8")
