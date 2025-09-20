import pytest

import config as cfg_module
from config import clear_settings_cache, get_settings


def test_load_existing_config():
    clear_settings_cache()
    settings = get_settings()
    assert settings.llm.model == "llama3.2:3b"
    assert settings.llm.backend == "ollama"
    assert settings.logging.fallback_level == "INFO"


def test_missing_base_file(monkeypatch):
    def raise_not_found(_path):
        raise FileNotFoundError

    monkeypatch.setattr(cfg_module, "_read_toml", raise_not_found)
    clear_settings_cache()
    with pytest.raises(FileNotFoundError):
        get_settings()
