import os

from app.core import engine as engine_module


class _ProcessPlugin:
    name = "proc"

    def __init__(self) -> None:
        self.pid = os.getpid()

    def run(self) -> str:  # pragma: no cover - not used in test
        return ""


class _NoProcessPlugin:
    name = "no-proc"

    def run(self) -> str:  # pragma: no cover - not used in test
        return ""


def test_plugin_metrics_reports_cpu_and_memory(monkeypatch):
    monkeypatch.setattr(
        engine_module.plugins,
        "reload_plugins",
        lambda: [_ProcessPlugin(), _NoProcessPlugin()],
    )

    eng = engine_module.Engine()
    data = eng.plugin_metrics()

    assert any(entry["name"] == "proc" and entry["memory"] is not None for entry in data)
    assert any(entry["name"] == "no-proc" and entry["cpu"] is None for entry in data)
