import json
import os
import logging

from app.core import logging_setup


def test_logs_are_json(capfd):
    logging_setup.set_request_id("req-123")
    logging_setup.configure()
    logger = logging.getLogger("test")
    logger.info("hello world")
    out, err = capfd.readouterr()
    logging.shutdown()
    # clean up generated log file
    if os.path.exists("watcher.log"):
        os.remove("watcher.log")
    data = json.loads(out.strip())
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["request_id"] == "req-123"
    assert data["name"] == "test"
