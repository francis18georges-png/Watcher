import tkinter as tk
from types import SimpleNamespace

import pytest

from app.ui import main
from app.tools.plugins import LoadedPlugin, SUPPORTED_PLUGIN_API_VERSION


def _make_plugin(name: str, path: str) -> LoadedPlugin:
    return LoadedPlugin(
        name=name,
        module=path,
        attribute="Plugin",
        api_version=SUPPORTED_PLUGIN_API_VERSION,
        signature="dummy",
    )


def test_toggle_offline_updates_status_label():
    app = main.WatcherApp.__new__(main.WatcherApp)
    app.settings = SimpleNamespace(
        ui=SimpleNamespace(mode="Sur"),
        llm=SimpleNamespace(backend="ollama", model="llama3"),
    )

    class DummyEngine:
        def __init__(self) -> None:
            self._offline = False

        def set_offline_mode(self, value: bool) -> None:
            self._offline = bool(value)

        def is_offline(self) -> bool:
            return self._offline

    app.engine = DummyEngine()
    app.status_var = tk.StringVar(master=tk.Tcl())
    app.offline_var = tk.BooleanVar(master=tk.Tcl(), value=False)

    main.WatcherApp._update_status_label(app)
    assert "désactivé" in app.status_var.get()

    app.offline_var.set(True)
    main.WatcherApp._toggle_offline_mode(app)
    assert app.engine.is_offline() is True
    assert "activé" in app.status_var.get()


def test_collect_plugin_stats_matches_process(monkeypatch):
    app = main.WatcherApp.__new__(main.WatcherApp)
    plugins = [
        _make_plugin("alpha", "tests.alpha"),
        _make_plugin("beta", "tests.beta"),
    ]
    app.engine = SimpleNamespace(plugins=plugins)

    class DummyProcess:
        def __init__(self, import_path: str, cpu: float, rss_mb: float) -> None:
            self._path = import_path
            self._cpu = cpu
            self._rss = rss_mb * 1024 * 1024

        def cmdline(self):
            return ["python", "-m", "app.tools.plugins.runner", "--path", self._path]

        def cpu_percent(self, interval=None):  # noqa: ARG002
            return self._cpu

        def memory_info(self):
            return SimpleNamespace(rss=self._rss)

    def fake_iter():
        yield DummyProcess(plugins[0].import_path, 25.0, 64.0)

    monkeypatch.setattr(main.psutil, "process_iter", lambda: fake_iter())
    stats = main.WatcherApp._collect_plugin_stats(app)

    assert stats["alpha"]["cpu"] == pytest.approx(25.0)
    assert stats["alpha"]["memory"] == pytest.approx(64.0)
    assert stats["beta"]["cpu"] == pytest.approx(0.0)
    assert stats["beta"]["memory"] == pytest.approx(0.0)
