import importlib

from importlib import resources
from importlib.resources.abc import Traversable

from app.tools import plugins


def test_reload_plugins():
    manifest: Traversable = resources.files("app").joinpath("plugins.toml")
    with resources.as_file(manifest) as cfg_path:
        original = cfg_path.read_text(encoding="utf-8")

        assert all(
            plugin.module != "tests.dummy_plugin"
            for plugin in plugins.reload_plugins(cfg_path)
        )

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
            loaded = plugins.reload_plugins(cfg_path)
            dummy_plugin = next(
                plugin for plugin in loaded if plugin.module == "tests.dummy_plugin"
            )

            module = importlib.import_module(dummy_plugin.module)
            plugin_cls = getattr(module, dummy_plugin.attribute)
            plugin = plugin_cls()
            assert plugin.run() == "dummy plugin loaded"
        finally:
            cfg_path.write_text(original, encoding="utf-8")
