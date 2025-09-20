from pathlib import Path

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


def test_environment_variable_override(monkeypatch):
    monkeypatch.setenv("WATCHER_UI__MODE", "env_override")
    clear_settings_cache()
    try:
        settings = get_settings()
        assert settings.ui.mode == "env_override"
    finally:
        clear_settings_cache()


def test_env_file_override(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("WATCHER_LLM__MODEL=env-file\n", encoding="utf-8")

    monkeypatch.setitem(cfg_module.Settings.model_config, "env_file", str(env_file))
    monkeypatch.setitem(
        cfg_module.Settings.model_config, "env_file_encoding", "utf-8"
    )
    monkeypatch.setattr(cfg_module, "_ENV_CACHE", None, raising=False)
    clear_settings_cache()

    try:
        settings = get_settings()
        assert settings.llm.model == "env-file"
    finally:
        clear_settings_cache()
