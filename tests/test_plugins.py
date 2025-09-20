from importlib.metadata import EntryPoint
from types import SimpleNamespace

from app.core.engine import Engine
from app.core import sandbox
from app.tools import plugins
from app.tools.plugins import (
    LoadedPlugin,
    SUPPORTED_PLUGIN_API_VERSION,
    compute_module_signature,
)
from app.tools.plugins.hello import HelloPlugin


def test_hello_plugin_loaded_and_runs():
    engine = Engine()
    assert any(p.module == "app.tools.plugins.hello" for p in engine.plugins)
    assert "Hello from plugin" in engine.run_plugins()


def test_entry_point_plugin_loaded(monkeypatch):
    ep = EntryPoint(
        name="hello_ep",
        value="app.tools.plugins.hello:HelloPlugin",
        group="watcher.plugins",
    )

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [ep])
    result = plugins.discover_entry_point_plugins()
    assert any(p.module == "app.tools.plugins.hello" for p in result)


def test_entry_point_plugin_failure(monkeypatch):
    class BrokenEP:
        name = "broken"

        def load(self):  # pragma: no cover - used to simulate failure
            raise RuntimeError("boom")

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [BrokenEP()])
    assert plugins.discover_entry_point_plugins() == []


def test_invalid_plugin_skipped(monkeypatch):
    class BadPlugin:
        def run(self):  # pragma: no cover - trivial
            return "bad"

    class BadEP:
        name = "bad"

        def load(self):
            return BadPlugin

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [BadEP()])
    assert plugins.discover_entry_point_plugins() == []


def test_faulty_plugin_logged_and_skipped(caplog, capsys):
    engine = Engine()

    failing_sig = compute_module_signature("tests.failing_plugin")
    dummy_sig = compute_module_signature("tests.dummy_plugin")
    assert failing_sig is not None
    assert dummy_sig is not None

    engine.plugins = [
        LoadedPlugin(
            name="bad",
            module="tests.failing_plugin",
            attribute="FailingPlugin",
            api_version=SUPPORTED_PLUGIN_API_VERSION,
            signature=failing_sig,
        ),
        LoadedPlugin(
            name="dummy",
            module="tests.dummy_plugin",
            attribute="DummyPlugin",
            api_version=SUPPORTED_PLUGIN_API_VERSION,
            signature=dummy_sig,
        ),
    ]

    with caplog.at_level("ERROR"):
        outputs = engine.run_plugins()

    assert outputs == ["dummy plugin loaded"]
    log_messages = "\n".join(rec.getMessage() for rec in caplog.records)
    if not log_messages:
        captured = capsys.readouterr()
        log_messages = captured.err
    assert "failed with code" in log_messages


def test_run_plugins_tracks_active_processes(monkeypatch):
    engine = Engine()
    assert engine.plugins
    engine.plugins = engine.plugins[:1]

    snapshots: list[list[dict[str, object]]] = []

    def _fake_run(cmd, **kwargs):
        on_start = kwargs.get("on_start")
        snapshots.append(engine.get_sandbox_processes())
        if callable(on_start):
            proc = SimpleNamespace(pid=54321)
            on_start(proc)
            snapshots.append(engine.get_sandbox_processes())
        return sandbox.SandboxResult(code=0, out="tracked output")

    monkeypatch.setattr("app.core.engine.sandbox.run", _fake_run)

    outputs = engine.run_plugins()

    assert outputs == ["tracked output"]
    assert engine.get_sandbox_processes() == []
    assert snapshots

    pre_start = snapshots[0]
    assert len(pre_start) == 1
    assert pre_start[0]["pid"] is None
    assert pre_start[0]["plugin"] is engine.plugins[0]

    post_start = next((snap for snap in snapshots if snap and snap[0].get("pid")), [])
    assert post_start
    assert post_start[0]["pid"] == 54321
    assert post_start[0]["import_path"] == engine.plugins[0].import_path
