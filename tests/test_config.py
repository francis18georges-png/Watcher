import pytest

from config import load_config
import config as cfg_module


def test_load_existing_config():
    cfg = load_config()
    assert cfg["llm"]["model"] == "llama3.2:3b"
    assert cfg["llm"]["backend"] == "ollama"


def test_missing_base_file(monkeypatch):
    monkeypatch.setattr(cfg_module, "_read_toml", lambda path: {})
    load_config.cache_clear()
    with pytest.raises(FileNotFoundError):
        load_config()
