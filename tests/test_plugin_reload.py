from pathlib import Path

from app.core.engine import Engine
from tests.dummy_plugin import DummyPlugin


def test_reload_plugins():
    cfg = Path("plugins.toml")
    original = cfg.read_text(encoding="utf-8")
    engine = Engine()
    assert not any(isinstance(p, DummyPlugin) for p in engine.plugins)

    cfg.write_text(
        original
        + "\n[[plugins]]\npath = \"tests.dummy_plugin:DummyPlugin\"\n",
        encoding="utf-8",
    )
    try:
        engine.reload_plugins()
        assert any(isinstance(p, DummyPlugin) for p in engine.plugins)
        outputs = engine.run_plugins()
        assert "dummy plugin loaded" in outputs
    finally:
        cfg.write_text(original, encoding="utf-8")

