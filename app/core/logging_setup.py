"""Utilities to configure structured JSON logging for the application."""

from __future__ import annotations

import logging
import logging.config
import datetime
import json
import os
import random
from pathlib import Path
from typing import Any
import importlib.resources as resources
from contextvars import ContextVar

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None


LOGGER_NAME = "watcher"
"""Base logger name used throughout the project."""


logger = logging.getLogger(LOGGER_NAME)
"""Central application logger.

Modules obtain child loggers with :func:`get_logger` ensuring that all logs
propagate through a single named hierarchy rooted at ``watcher``. The logger is
initially configured with ``NOTSET`` level so that the global configuration
controls the effective verbosity.
"""

logger.setLevel(logging.NOTSET)


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")
sample_rate_ctx: ContextVar[float | None] = ContextVar("sample_rate", default=None)


class RequestIdFilter(logging.Filter):
    """Logging filter to inject contextual identifiers into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - simple
        request_id = request_id_ctx.get("")
        trace_id = trace_id_ctx.get("")
        sample_rate = sample_rate_ctx.get(None)
        record.request_id = request_id
        if trace_id:
            record.trace_id = trace_id
        if sample_rate is not None and not hasattr(record, "sample_rate"):
            record.sample_rate = sample_rate
        return True


class SamplingFilter(logging.Filter):
    """Probabilistically drop log records based on a sampling rate."""

    def __init__(self, name: str = "", sample_rate: float = 1.0) -> None:
        super().__init__(name)
        self.sample_rate = self._validate_rate(sample_rate)

    @staticmethod
    def _validate_rate(rate: float) -> float:
        try:
            rate_value = float(rate)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("sample_rate must be a number between 0 and 1") from exc
        if not 0.0 <= rate_value <= 1.0:
            raise ValueError("sample_rate must be between 0 and 1")
        return rate_value

    def filter(self, record: logging.LogRecord) -> bool:
        rate = sample_rate_ctx.get(None)
        if rate is None:
            rate = self.sample_rate
        else:
            rate = self._validate_rate(rate)

        record.sample_rate = rate
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        return random.random() < rate


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def __init__(self, *args: object, sample_rate: float | None = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.default_sample_rate = sample_rate

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id") and record.request_id:
            log_record["request_id"] = record.request_id
        if hasattr(record, "trace_id") and record.trace_id:
            log_record["trace_id"] = record.trace_id
        sample_rate = getattr(record, "sample_rate", None)
        if sample_rate is None:
            sample_rate = self.default_sample_rate
        if sample_rate is not None:
            log_record["sample_rate"] = sample_rate
        return json.dumps(log_record)


def set_request_id(request_id: str) -> None:
    """Set the request identifier for subsequent log records."""
    request_id_ctx.set(request_id)


def set_trace_context(
    trace_id: str | None = None, *, sample_rate: float | None = None
) -> None:
    """Set tracing information used when emitting structured logs."""

    trace_id_ctx.set(trace_id or "")
    sample_rate_ctx.set(sample_rate)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the application logger or one of its children.

    Parameters
    ----------
    name:
        Optional child logger name. When provided the logger returned is
        ``watcher.<name>`` which still propagates through the central ``watcher``
        logger.
    """

    return logger if name is None else logger.getChild(name)


def _matches_target(candidate: object, expected: type[object]) -> bool:
    """Return whether ``candidate`` refers to ``expected``."""

    if candidate is None:
        return False
    if candidate is expected:
        return True
    if isinstance(candidate, type):
        try:
            return issubclass(candidate, expected)
        except TypeError:  # pragma: no cover - defensive
            return False
    if isinstance(candidate, str):
        normalized = candidate.replace(":", ".")
        qualified_name = f"{expected.__module__}.{expected.__qualname__}"
        return normalized == qualified_name
    return False


def _apply_sample_rate(config: dict[str, Any], sample_rate: float | None) -> None:
    """Inject the configured sample rate into known filters and formatters."""

    if sample_rate is None:
        return

    filters = config.get("filters")
    if isinstance(filters, dict):
        for filter_config in filters.values():
            if not isinstance(filter_config, dict):
                continue
            if any(
                _matches_target(filter_config.get(key), SamplingFilter)
                for key in ("()", "class")
            ):
                filter_config["sample_rate"] = sample_rate

    formatters = config.get("formatters")
    if isinstance(formatters, dict):
        for formatter_config in formatters.values():
            if not isinstance(formatter_config, dict):
                continue
            if any(
                _matches_target(formatter_config.get(key), JSONFormatter)
                for key in ("()", "class")
            ):
                formatter_config["sample_rate"] = sample_rate


def _set_formatter_sample_rate(sample_rate: float | None) -> None:
    """Ensure instantiated formatters know about the configured sample rate."""

    if sample_rate is None:
        return

    seen_handlers: set[int] = set()
    loggers_to_check: list[logging.Logger] = [logging.getLogger(), logger]

    for existing in logging.root.manager.loggerDict.values():
        if isinstance(existing, logging.Logger):
            loggers_to_check.append(existing)

    for current in loggers_to_check:
        for handler in getattr(current, "handlers", []):
            handler_id = id(handler)
            if handler_id in seen_handlers:
                continue
            seen_handlers.add(handler_id)
            formatter = handler.formatter
            if isinstance(formatter, JSONFormatter):
                formatter.default_sample_rate = sample_rate


def _configure_from_path(
    config_path: Path,
    *,
    fallback_level: int | str | None = logging.INFO,
    sample_rate: float | None = None,
) -> None:
    """Load logging configuration from ``config_path`` if possible."""

    if not config_path.exists():  # pragma: no cover - config file missing
        level = fallback_level
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        if not isinstance(level, int):
            level = logging.INFO
        logging.basicConfig(level=level)
        return

    suffix = config_path.suffix.lower()
    if suffix == ".json":
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        _apply_sample_rate(config, sample_rate)
        logging.config.dictConfig(config)
        _set_formatter_sample_rate(sample_rate)
        return

    if yaml:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        _apply_sample_rate(config, sample_rate)
        logging.config.dictConfig(config)
        _set_formatter_sample_rate(sample_rate)
        return

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "app.core.logging_setup.JSONFormatter",
            }
        },
        "filters": {
            "request_id": {"()": "app.core.logging_setup.RequestIdFilter"},
            "sampling": {
                "()": "app.core.logging_setup.SamplingFilter",
                "sample_rate": 1.0,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "json",
                "filters": ["request_id", "sampling"],
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "json",
                "filters": ["request_id", "sampling"],
                "filename": "watcher.log",
            },
        },
        "root": {"level": "INFO", "handlers": ["console", "file"]},
    }
    _apply_sample_rate(config, sample_rate)
    logging.config.dictConfig(config)
    _set_formatter_sample_rate(sample_rate)


def configure(*, sample_rate: float | None = None) -> None:
    """Configure logging from the YAML configuration file if possible."""
    from config import get_settings

    settings = get_settings()
    fallback_level = getattr(logging, settings.logging.fallback_level, logging.INFO)

    config_path = settings.logging.config_path
    if config_path is not None:
        resolved = settings.paths.resolve(config_path)
        _configure_from_path(
            resolved, fallback_level=fallback_level, sample_rate=sample_rate
        )
        logger.setLevel(logging.NOTSET)
        return

    env_path = os.environ.get("LOGGING_CONFIG_PATH")
    if env_path:
        _configure_from_path(
            Path(env_path), fallback_level=fallback_level, sample_rate=sample_rate
        )
        logger.setLevel(logging.NOTSET)
        return

    resource = resources.files("config") / "logging.yml"
    try:
        with resources.as_file(resource) as config_path:
            _configure_from_path(
                config_path, fallback_level=fallback_level, sample_rate=sample_rate
            )
    except FileNotFoundError:  # pragma: no cover - config resource missing
        logging.basicConfig(level=fallback_level)
    # Ensure application logger does not filter messages on its own and relies
    # on the configured handlers of the root logger instead.
    logger.setLevel(logging.NOTSET)
