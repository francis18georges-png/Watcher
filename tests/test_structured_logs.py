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


def test_configure_overrides_sample_rate(monkeypatch):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    _cleanup()
    logging_setup.configure(sample_rate=0.2)
    try:
        root_logger = logging.getLogger()
        sampling_rates = []
        formatter_rates = []
        for handler in root_logger.handlers:
            for flt in handler.filters:
                if isinstance(flt, logging_setup.SamplingFilter):
                    sampling_rates.append(flt.sample_rate)
            formatter = handler.formatter
            if isinstance(formatter, logging_setup.JSONFormatter):
                formatter_rates.append(formatter.default_sample_rate)

        assert sampling_rates and all(rate == 0.2 for rate in sampling_rates)
        assert formatter_rates and all(rate == 0.2 for rate in formatter_rates)
    finally:
        _cleanup()


def test_configure_uses_json_config_via_env(tmp_path, monkeypatch, capfd):
    config_path = tmp_path / "custom_logging.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "json": {
                        "()": "app.core.logging_setup.JSONFormatter",
                        "sample_rate": 0.3,
                    }
                },
                "filters": {
                    "request_id": {
                        "()": "app.core.logging_setup.RequestIdFilter"
                    },
                    "sampling": {
                        "()": "app.core.logging_setup.SamplingFilter",
                        "sample_rate": 0.3,
                    },
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "json",
                        "filters": ["request_id", "sampling"],
                        "stream": "ext://sys.stdout",
                    }
                },
                "root": {"level": "INFO", "handlers": ["console"]},
            }
        )
    )

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_path))
    _cleanup()
    logging_setup.set_request_id("req-json")
    logging_setup.set_trace_context(trace_id="trace-json")
    logging_setup.configure()
    try:
        monkeypatch.setattr(logging_setup.random, "random", lambda: 0.1)
        logger = logging_setup.get_logger("json")
        logger.info("hello json config")
        out, err = capfd.readouterr()
        data = json.loads(out.strip())
        assert data["name"] == "watcher.json"
        assert data["trace_id"] == "trace-json"
        assert data["sample_rate"] == 0.3
    finally:
        _cleanup()
        logging_setup.set_trace_context()
        logging_setup.set_request_id("")
