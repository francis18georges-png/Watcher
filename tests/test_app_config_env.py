from app.config import load_config


def test_env_override(monkeypatch):
    # default value from settings.toml
    base = load_config("ui")
    assert base["mode"] == "Sur"

    monkeypatch.setenv("WATCHER_ENV", "dev")
    cfg = load_config("ui")
    assert cfg["mode"] == "dev"
    assert cfg["theme"] == "dark"  # value from base config persists
