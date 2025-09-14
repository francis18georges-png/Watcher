from importlib.metadata import EntryPoint

from app.core.engine import Engine
from app.tools import plugins
from app.tools.plugins.hello import HelloPlugin


def test_hello_plugin_loaded_and_runs():
    engine = Engine()
    assert any(isinstance(p, HelloPlugin) for p in engine.plugins)
    assert "Hello from plugin" in engine.run_plugins()


def test_entry_point_plugin_loaded(monkeypatch):
    ep = EntryPoint(
        name="hello_ep",
        value="app.tools.plugins.hello:HelloPlugin",
        group="watcher.plugins",
    )

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [ep])
    result = plugins.discover_entry_point_plugins()
    assert any(isinstance(p, HelloPlugin) for p in result)


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


def test_faulty_plugin_logged_and_skipped(caplog):
    engine = Engine()

    class BadPlugin:
        name = "bad"

        def run(self):
            raise RuntimeError("boom")

    # Bad plugin first to ensure subsequent plugins still run
    engine.plugins = [BadPlugin(), HelloPlugin()]

    with caplog.at_level("ERROR"):
        outputs = engine.run_plugins()

    assert outputs == ["Hello from plugin"]
    assert any("Plugin bad failed" in rec.getMessage() for rec in caplog.records)
