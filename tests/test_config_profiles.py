import logging

from config import clear_settings_cache, get_settings


def test_dev_profile():
    clear_settings_cache()
    cfg = get_settings(environment="dev")
    assert cfg.ui.mode == "dev"
    assert cfg.ui.theme == "dark"
    clear_settings_cache()


def test_prod_profile():
    clear_settings_cache()
    cfg = get_settings(environment="prod")
    assert cfg.ui.mode == "prod"
    assert cfg.ui.theme == "dark"
    clear_settings_cache()


def test_missing_profile_logs_warning(caplog):
    clear_settings_cache()
    with caplog.at_level(logging.WARNING):
        get_settings(environment="missing")
    assert any(
        "Profile configuration file not found" in record.message
        for record in caplog.records
    )
    clear_settings_cache()
