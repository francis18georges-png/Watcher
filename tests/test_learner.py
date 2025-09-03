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


def test_suggest_and_history(tmp_path: Path) -> None:
    bench = DummyBench({"base": 0.2, "base_1": 0.3, "base_1_2": 0.4})
    learner = Learner(bench, tmp_path)
    assert learner.current_best() == "base"
    v1 = learner.suggest()
    assert v1 == "base_1"
    learner.compare("base", v1)
    history = (tmp_path / "history.jsonl").read_text().strip().splitlines()
    assert len(history) == 1
    rec = json.loads(history[0])
    assert rec["best"]["name"] == v1
    v2 = learner.suggest()
    assert v2 == "base_1_2"
