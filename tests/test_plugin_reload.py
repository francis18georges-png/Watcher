from importlib import resources
from importlib.resources.abc import Traversable

from app.core.engine import Engine
from app.tools import plugins


def test_reload_plugins():
    manifest: Traversable = resources.files("app").joinpath("plugins.toml")
    with resources.as_file(manifest) as cfg_path:
        original = cfg_path.read_text(encoding="utf-8")

        engine = Engine()
        assert not any(p.module == "tests.dummy_plugin" for p in engine.plugins)

        signature = plugins.compute_module_signature("tests.dummy_plugin")
        assert signature is not None

        cfg_path.write_text(
            original
            + "\n[[plugins]]\n"
            + 'path = "tests.dummy_plugin:DummyPlugin"\n'
            + 'api_version = "1.0"\n'
            + f'signature = "{signature}"\n',
            encoding="utf-8",
        )
        try:
            engine.reload_plugins()
            assert any(p.module == "tests.dummy_plugin" for p in engine.plugins)
            outputs = engine.run_plugins()
            assert "dummy plugin loaded" in outputs
        finally:
            cfg_path.write_text(original, encoding="utf-8")
