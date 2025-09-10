from pathlib import Path
import json

from app.core.learner import Learner
from app.core.benchmark import Bench


class DummyBench(Bench):
    def __init__(self, scores: dict[str, float]):
        self.scores = scores

    def run_variant(self, name: str) -> float:  # type: ignore[override]
        return self.scores[name]


def test_compare_persists_best(tmp_path: Path) -> None:
    bench = DummyBench({"A": 0.1, "B": 0.9})
    learner = Learner(bench, tmp_path)
    res = learner.compare("A", "B")
    assert res["best"]["name"] == "B"
    saved = json.loads((tmp_path / "best_variant.json").read_text())
    assert saved["name"] == "B"

    bench.scores["A"] = 0.8
    res2 = learner.compare("A", "B")
    assert res2["best"]["name"] == "B"


def test_step_handles_empty_state(tmp_path: Path) -> None:
    bench = DummyBench({})
    learner = Learner(bench, tmp_path)
    assert learner.step([], reward=1.0) == []
