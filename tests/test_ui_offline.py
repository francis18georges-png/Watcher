"""Tests for the offline monitoring helpers used by the Tkinter UI."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ui import main


class _DummyProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._cpu_calls = 0

    def cpu_percent(self, interval: float | None = None) -> float:  # noqa: ARG002
        self._cpu_calls += 1
        return 0.0 if self._cpu_calls == 1 else 37.5

    def memory_info(self):  # pragma: no cover - trivial structure
        return SimpleNamespace(rss=1024, vms=2048)

    def num_threads(self) -> int:
        return 2

    def name(self) -> str:
        return "python"


def test_collect_plugin_stats_uses_cached_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    app = main.WatcherApp.__new__(main.WatcherApp)
    app._plugin_process_cache = {}

    created: dict[int, _DummyProcess] = {}
    creations = 0

    def _fake_process(pid: int) -> _DummyProcess:
        nonlocal creations
        creations += 1
        created.setdefault(pid, _DummyProcess(pid))
        return created[pid]

    monkeypatch.setattr(main.psutil, "Process", _fake_process)

    plugin = SimpleNamespace(import_path="tests.dummy_plugin:DummyPlugin", name="dummy")
    entry = SimpleNamespace(pid=4242, plugin=plugin)

    first = app._collect_plugin_stats([entry])
    assert len(first) == 1
    assert first[0]["cpu_percent"] == pytest.approx(0.0)

    second = app._collect_plugin_stats([entry])
    assert len(second) == 1
    assert second[0]["cpu_percent"] == pytest.approx(37.5)

    assert creations == 1
    assert created[4242]._cpu_calls == 2
