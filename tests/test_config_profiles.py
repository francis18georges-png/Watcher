import logging

from config import load_config


def test_dev_profile():
    cfg = load_config(profile="dev")
    assert cfg["ui"]["mode"] == "dev"
    assert cfg["ui"]["theme"] == "dark"


def test_prod_profile():
    cfg = load_config(profile="prod")
    assert cfg["ui"]["mode"] == "prod"
    assert cfg["ui"]["theme"] == "dark"


def test_missing_profile_logs_warning(caplog):
    load_config.cache_clear()
    with caplog.at_level(logging.WARNING):
        load_config(profile="missing")
    assert any(
        "Profile configuration file not found" in record.message
        for record in caplog.records
    )
