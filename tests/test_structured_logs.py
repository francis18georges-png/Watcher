import json
import os
import logging

from app.core import logging_setup


def _cleanup() -> None:
    logging.shutdown()
    logging.getLogger().handlers.clear()
    if os.path.exists("watcher.log"):
        os.remove("watcher.log")


def test_logs_are_json(capfd, monkeypatch):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    logging_setup.set_request_id("req-123")
    logging_setup.configure()
    logger = logging.getLogger("test")
    logger.info("hello world")
    out, err = capfd.readouterr()
    _cleanup()
    data = json.loads(out.strip())
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["request_id"] == "req-123"
    assert data["name"] == "test"


def test_basic_logging_when_config_missing(capfd, monkeypatch):
    monkeypatch.setenv("LOGGING_CONFIG_PATH", "missing.yml")
    _cleanup()
    logging_setup.configure()
    logger = logging.getLogger("test")
    logger.info("hello world")
    out, err = capfd.readouterr()
    _cleanup()
    assert err.strip() == "INFO:test:hello world"
