from config import clear_settings_cache, get_settings


def test_env_override(monkeypatch):
    # default value from settings.toml
    clear_settings_cache()
    base = get_settings().ui
    assert base.mode == "Sur"

    monkeypatch.setenv("WATCHER_ENV", "dev")
    clear_settings_cache()
    cfg = get_settings().ui
    assert cfg.mode == "dev"
    assert cfg.theme == "dark"  # value from base config persists
    clear_settings_cache()
