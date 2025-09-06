from app.core.engine import Engine
from app.tools.plugins.hello import HelloPlugin


def test_hello_plugin_loaded_and_runs():
    engine = Engine()
    assert any(isinstance(p, HelloPlugin) for p in engine.plugins)
    assert "Hello from plugin" in engine.run_plugins()
