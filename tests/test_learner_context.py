import numpy as np
from app.core.engine import Engine
import math

from app.core.memory import Memory
from app.core.learner import Learner
from app.core.benchmark import Bench


class DummyBench(Bench):
    def run_variant(self, name: str) -> float:  # type: ignore[override]
        return 0.0


def _setup_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.memory.embed_ollama",
        lambda texts, model="nomic-embed-text": [np.array([1.0])],
    )

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.base = tmp_path
    eng.prepare_data = lambda: "data"

    class DummyQG:
        def run_all(self):
            return {"ok": True, "results": {}}

    eng.qg = DummyQG()

    bench = DummyBench()
    eng.learner = Learner(bench, tmp_path)

    monkeypatch.setattr("app.core.autograder.grade_all", lambda: {"ok": True})

    return eng


def test_parameter_updates_over_iterations(tmp_path, monkeypatch):
    eng = _setup_engine(tmp_path, monkeypatch)

    eng.auto_improve(qg_res="{}", state=[1.0, 0.0], reward=1.0)
    assert eng.learner.params == [0.0, 0.0]

    eng.auto_improve(qg_res="{}", state=[0.0, 1.0], reward=-1.0)
    assert math.isclose(eng.learner.params[0], -0.1, abs_tol=1e-6)
    assert math.isclose(eng.learner.params[1], 0.1, abs_tol=1e-6)

    eng.auto_improve(qg_res="{}", state=[1.0, 1.0], reward=2.0)
    assert math.isclose(eng.learner.params[0], -0.2, abs_tol=1e-6)
    assert math.isclose(eng.learner.params[1], 0.2, abs_tol=1e-6)
