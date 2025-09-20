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


class _DummyTree:
    def __init__(self) -> None:
        self.rows: dict[str, tuple] = {}
        self._counter = 0

    def get_children(self):
        return list(self.rows.keys())

    def delete(self, item):  # pragma: no cover - simple container helper
        self.rows.pop(item, None)

    def insert(self, parent, index, values):  # noqa: ARG002
        item_id = f"item{self._counter}"
        self._counter += 1
        self.rows[item_id] = values
        return item_id


class _DummyVar:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:  # pragma: no cover - optional helper
        self.value = value


class _DummyLabel:
    def __init__(self) -> None:
        self.kwargs: dict[str, str] = {}

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)


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


def test_render_plugin_stats_formats_values() -> None:
    app = main.WatcherApp.__new__(main.WatcherApp)
    app.plugin_tree = _DummyTree()
    stats = [
        {
            "plugin_name": "dummy",
            "import_path": "tests.dummy_plugin:DummyPlugin",
            "pid": 111,
            "cpu_percent": 12.345,
            "rss": 10 * 1024 * 1024,
            "vms": 20 * 1024 * 1024,
            "num_threads": 3,
            "process_name": "python",
        }
    ]

    main.WatcherApp._render_plugin_stats(app, stats)
    values = list(app.plugin_tree.rows.values())[0]
    assert values == ("dummy", 111, "12.3", "10.0", "20.0", 3, "python")


def test_update_plugin_monitor_schedules_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    app = main.WatcherApp.__new__(main.WatcherApp)
    app.plugin_tree = _DummyTree()
    app._plugin_refresh_interval_ms = 1234
    app._plugin_refresh_job = None
    app.winfo_exists = lambda: True

    stats = [
        {
            "plugin_name": "dummy",
            "import_path": "tests.dummy_plugin:DummyPlugin",
            "pid": 222,
            "cpu_percent": 1.0,
            "rss": 0,
            "vms": 0,
            "num_threads": 1,
            "process_name": "python",
        }
    ]

    def fake_collect(entries=None):  # noqa: ARG001
        app._plugin_stats_snapshot = stats
        return stats

    app._collect_plugin_stats = fake_collect  # type: ignore[assignment]

    calls: dict[str, object] = {}

    def fake_after(delay: int, callback):
        calls["delay"] = delay
        calls["callback"] = callback
        return "job-id"

    def fake_after_cancel(job):
        calls.setdefault("cancelled", []).append(job)

    app.after = fake_after  # type: ignore[assignment]
    app.after_cancel = fake_after_cancel  # type: ignore[assignment]

    main.WatcherApp._update_plugin_monitor(app)
    assert calls["delay"] == 1234
    assert app._plugin_refresh_job == "job-id"
    assert list(app.plugin_tree.rows.values()) == [("dummy", 222, "1.0", "0.0", "0.0", 1, "python")]


def test_toggle_offline_updates_engine() -> None:
    class _Engine:
        def __init__(self) -> None:
            self.offline_mode = False
            self.calls: list[bool] = []

        def set_offline_mode(self, offline: bool) -> None:
            self.offline_mode = offline
            self.calls.append(offline)

    app = main.WatcherApp.__new__(main.WatcherApp)
    app.engine = _Engine()
    app.offline_var = _DummyVar(True)
    app.status = _DummyLabel()
    app.settings = SimpleNamespace(
        llm=SimpleNamespace(backend="stub-backend", model="stub-model")
    )

    main.WatcherApp._toggle_offline(app)
    assert app.engine.offline_mode is True
    assert app.engine.calls == [True]
    assert "Offline" in app.status.kwargs.get("text", "")
