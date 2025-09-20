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
    logging_setup.set_trace_context(trace_id="trace-abc", sample_rate=0.5)
    logging_setup.configure()
    logger = logging_setup.get_logger("test")
    monkeypatch.setattr(logging_setup.random, "random", lambda: 0.1)
    logger.info("hello world")
    out, err = capfd.readouterr()
    _cleanup()
    logging_setup.set_trace_context()
    data = json.loads(out.strip())
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["request_id"] == "req-123"
    assert data["name"] == "watcher.test"
    assert data["trace_id"] == "trace-abc"
    assert data["sample_rate"] == 0.5


def test_basic_logging_when_config_missing(capfd, monkeypatch):
    monkeypatch.setenv("LOGGING_CONFIG_PATH", "missing.yml")
    _cleanup()
    logging_setup.set_trace_context()
    logging_setup.configure()
    logger = logging_setup.get_logger("test")
    logger.info("hello world")
    out, err = capfd.readouterr()
    _cleanup()
    assert err.strip() == "INFO:watcher.test:hello world"


def test_errors_are_logged(capfd, monkeypatch):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    _cleanup()
    logging_setup.set_trace_context(trace_id="trace-error", sample_rate=1.0)
    logging_setup.configure()
    logger = logging_setup.get_logger("test")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")
    out, err = capfd.readouterr()
    _cleanup()
    logging_setup.set_trace_context()
    data = json.loads(out.strip())
    assert data["level"] == "ERROR"
    assert data["message"] == "failed"
    assert data["trace_id"] == "trace-error"


def test_sampling_filter_respects_context(monkeypatch):
    record = logging.LogRecord(
        name="watcher.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="payload",
        args=(),
        exc_info=None,
    )
    flt = logging_setup.SamplingFilter(sample_rate=0.2)
    logging_setup.set_trace_context(sample_rate=0.4)
    monkeypatch.setattr(logging_setup.random, "random", lambda: 0.3)
    try:
        assert flt.filter(record) is True
        assert record.sample_rate == 0.4
    finally:
        logging_setup.set_trace_context()


def test_sampling_filter_blocks_when_probability_low(monkeypatch):
    record = logging.LogRecord(
        name="watcher.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="payload",
        args=(),
        exc_info=None,
    )
    flt = logging_setup.SamplingFilter(sample_rate=0.5)
    monkeypatch.setattr(logging_setup.random, "random", lambda: 0.9)
    assert flt.filter(record) is False
    assert record.sample_rate == 0.5


def test_configure_applies_sample_rate_to_formatter_class(
    tmp_path, capfd, monkeypatch
):
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "class": "app.core.logging_setup.JSONFormatter",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
    config_path = tmp_path / "logging.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_path))
    _cleanup()
    logging_setup.set_trace_context()

    logging_setup.configure(sample_rate=0.2)
    logger = logging_setup.get_logger("test")
    logger.info("sample")

    out, err = capfd.readouterr()
    _cleanup()
    logging_setup.set_trace_context()

    assert err == ""
    data = json.loads(out.strip())
    assert data["sample_rate"] == 0.2


def test_configure_supports_custom_field_names(tmp_path, capfd, monkeypatch):
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "app.core.logging_setup.JSONFormatter",
                "request_id_field": "requestId",
                "trace_id_field": "traceId",
                "sample_rate_field": "sampleRate",
            }
        },
        "filters": {
            "request": {
                "()": "app.core.logging_setup.RequestIdFilter",
                "request_id_field": "requestId",
                "trace_id_field": "traceId",
                "sample_rate_field": "sampleRate",
            },
            "sampling": {
                "()": "app.core.logging_setup.SamplingFilter",
                "sample_rate": 1.0,
                "sample_rate_field": "sampleRate",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "json",
                "filters": ["request", "sampling"],
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
    config_path = tmp_path / "logging.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_path))

    _cleanup()
    logging_setup.set_request_id("req-999")
    logging_setup.set_trace_context(trace_id="trace-custom", sample_rate=0.4)
    logging_setup.configure()
    logger = logging_setup.get_logger("test")
    monkeypatch.setattr(logging_setup.random, "random", lambda: 0.1)
    logger.info("payload")

    out, err = capfd.readouterr()
    _cleanup()
    logging_setup.set_trace_context()

    assert err == ""
    data = json.loads(out.strip())
    assert data["requestId"] == "req-999"
    assert data["traceId"] == "trace-custom"
    assert data["sampleRate"] == 0.4
