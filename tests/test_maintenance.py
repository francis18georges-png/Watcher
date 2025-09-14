from pathlib import Path

from app.utils import np

from app.core.engine import Engine
from app.core.memory import Memory

try:
    import tomllib
except ModuleNotFoundError:  # Python <3.11
    import tomli as tomllib


def _setup_engine(tmp_path, monkeypatch, calls):
    """Create a light-weight Engine instance for testing."""

    # Avoid heavy embedding work when Memory.add is called
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
            calls.append("run_all")
            return {"pytest": {"ok": True, "out": "", "err": ""}}

    class DummyLearner:
        def compare(self, a, b):
            return {"A": 0.0, "B": 0.0, "best": {"name": "A"}}

    eng.qg = DummyQG()
    eng.learner = DummyLearner()

    monkeypatch.setattr("app.core.autograder.grade_all", lambda: {"ok": True})

    return eng


def test_perform_maintenance_reuses_quality_gate(tmp_path, monkeypatch):
    calls: list[str] = []
    eng = _setup_engine(tmp_path, monkeypatch, calls)
    eng.perform_maintenance()
    assert calls == ["run_all"]


def test_auto_improve_runs_quality_when_missing(tmp_path, monkeypatch):
    calls: list[str] = []
    eng = _setup_engine(tmp_path, monkeypatch, calls)
    eng.auto_improve()
    assert calls == ["run_all"]


def test_pyproject_has_black_and_ruff():
    pyproject = Path("pyproject.toml")
    config = tomllib.loads(pyproject.read_text())
    assert "tool" in config
    assert "black" in config["tool"]
    assert "ruff" in config["tool"]
