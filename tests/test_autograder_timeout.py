import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.core import autograder


def _create_timeout_task(tmp_path: pathlib.Path) -> pathlib.Path:
    task_dir = tmp_path / "slow_task"
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_sleep.py"
    test_file.write_text(
        "import time\n\n" "def test_sleep():\n    time.sleep(2)\n"
    )
    return task_dir


def test_run_pytest_timeout(tmp_path):
    task_dir = _create_timeout_task(tmp_path)
    rep = autograder._run_pytest(task_dir, timeout=1)
    assert rep == {
        "ok": False,
        "timeout": True,
        "sec": 1,
        "stdout": "",
        "stderr": "timeout",
    }


def test_grade_task_timeout(tmp_path, monkeypatch):
    task_dir = tmp_path / "task1"
    task_dir.mkdir()
    monkeypatch.setattr(autograder, "DATASETS", tmp_path)

    def fake_run_pytest(_task, timeout=60):
        return {
            "ok": False,
            "timeout": True,
            "sec": timeout,
            "stdout": "",
            "stderr": "timeout",
        }

    monkeypatch.setattr(autograder, "_run_pytest", fake_run_pytest)
    rep = autograder.grade_task("task1")
    assert rep["timeout"] is True
    assert rep["score"] == 0.0


def test_grade_all_timeout(tmp_path, monkeypatch):
    slow = tmp_path / "slow"
    fast = tmp_path / "fast"
    slow.mkdir()
    fast.mkdir()
    monkeypatch.setattr(autograder, "DATASETS", tmp_path)

    def fake_run_pytest(task_path, timeout=60):
        if task_path.name == "slow":
            return {
                "ok": False,
                "timeout": True,
                "sec": timeout,
                "stdout": "",
                "stderr": "timeout",
            }
        return {
            "ok": True,
            "timeout": False,
            "sec": 0.1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(autograder, "_run_pytest", fake_run_pytest)
    rep = autograder.grade_all()
    assert rep["timeout"] is True
    timeouts = [r["timeout"] for r in rep["results"]]
    assert timeouts == [True, False] or timeouts == [False, True]
