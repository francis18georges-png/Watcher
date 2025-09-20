from importlib.metadata import EntryPoint

from app.core.engine import Engine
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


def test_faulty_plugin_logged_and_skipped(caplog):
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
    assert any("failed with code" in rec.getMessage() for rec in caplog.records)
