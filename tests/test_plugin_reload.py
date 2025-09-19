from importlib import resources
from importlib.resources.abc import Traversable

from app.core.engine import Engine
from tests.dummy_plugin import DummyPlugin


def test_reload_plugins():
    manifest: Traversable = resources.files("app").joinpath("plugins.toml")
    with resources.as_file(manifest) as cfg_path:
        original = cfg_path.read_text(encoding="utf-8")

        engine = Engine()
        assert not any(isinstance(p, DummyPlugin) for p in engine.plugins)

        cfg_path.write_text(
            original + '\n[[plugins]]\npath = "tests.dummy_plugin:DummyPlugin"\n',
            encoding="utf-8",
        )
        try:
            engine.reload_plugins()
            assert any(isinstance(p, DummyPlugin) for p in engine.plugins)
            outputs = engine.run_plugins()
            assert "dummy plugin loaded" in outputs
        finally:
            cfg_path.write_text(original, encoding="utf-8")
