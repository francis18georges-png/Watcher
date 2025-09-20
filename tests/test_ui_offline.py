"""Tests for the offline monitoring helpers used by the Tkinter UI."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import sandbox
from app.core.engine import Engine
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


class _DummyTreeview:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def get_children(self):
        return [str(index) for index in range(len(self.rows))]

    def delete(self, *item_ids) -> None:
        if not item_ids:
            self.rows.clear()
            return

        indices: list[int] = []
        for item in item_ids:
            try:
                indices.append(int(item))
            except (TypeError, ValueError):
                continue
        if not indices:
            self.rows.clear()
            return
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self.rows):
                del self.rows[index]

    def insert(self, parent, index, iid=None, **kwargs):  # noqa: D401 - Tkinter compat
        values = kwargs.get("values")
        text = kwargs.get("text", "")
        self.rows.append({"values": values, "text": text})
        return iid or str(len(self.rows) - 1)


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


def test_update_plugin_monitor_populates_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Engine()
    assert engine.plugins
    engine.plugins = engine.plugins[:1]

    snapshots: list[list[dict[str, Any]]] = []

    def _fake_run(cmd, **kwargs):
        on_start = kwargs.get("on_start")
        snapshots.append(engine.get_sandbox_processes())
        if callable(on_start):
            proc = SimpleNamespace(pid=67890)
            on_start(proc)
            snapshots.append(engine.get_sandbox_processes())
        return sandbox.SandboxResult(code=0, out="ui output")

    monkeypatch.setattr("app.core.engine.sandbox.run", _fake_run)

    engine.run_plugins()

    populated = next((snap for snap in snapshots if snap and snap[0].get("pid")), [])
    assert populated

    pid = populated[0]["pid"]
    assert isinstance(pid, int)

    def _fake_process(pid_value: int) -> _DummyProcess:
        return _DummyProcess(pid_value)

    monkeypatch.setattr(main.psutil, "Process", _fake_process)

    app = main.WatcherApp.__new__(main.WatcherApp)
    app.engine = SimpleNamespace(
        get_sandbox_processes=lambda: [dict(entry) for entry in populated]
    )
    app._plugin_process_cache = {}
    app._sandbox_processes = []
    app.plugin_tree = _DummyTreeview()
    app.after = lambda *args, **kwargs: None  # type: ignore[assignment]

    app._update_plugin_monitor()

    assert app._sandbox_processes
    assert len(app.plugin_tree.rows) == len(populated)
    assert app.plugin_tree.rows[0]["values"][0] == pid
