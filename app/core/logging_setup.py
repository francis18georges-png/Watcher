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

    def __init__(
        self,
        name: str = "",
        *,
        request_id_field: str = "request_id",
        trace_id_field: str = "trace_id",
        sample_rate_field: str = "sample_rate",
    ) -> None:
        super().__init__(name)
        self.request_id_field = request_id_field
        self.trace_id_field = trace_id_field
        self.sample_rate_field = sample_rate_field

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - simple
        request_id = request_id_ctx.get("")
        trace_id = trace_id_ctx.get("")
        sample_rate = sample_rate_ctx.get(None)
        setattr(record, self.request_id_field, request_id)
        if trace_id:
            setattr(record, self.trace_id_field, trace_id)
        if sample_rate is not None and not hasattr(record, self.sample_rate_field):
            setattr(record, self.sample_rate_field, sample_rate)
        return True


class SamplingFilter(logging.Filter):
    """Probabilistically drop log records based on a sampling rate."""

    def __init__(
        self,
        name: str = "",
        *,
        sample_rate: float = 1.0,
        sample_rate_field: str = "sample_rate",
    ) -> None:
        super().__init__(name)
        self.sample_rate = self._validate_rate(sample_rate)
        self.sample_rate_field = sample_rate_field

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

        setattr(record, self.sample_rate_field, rate)
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        return random.random() < rate


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def __init__(
        self,
        *args: object,
        sample_rate: float | None = None,
        request_id_field: str = "request_id",
        trace_id_field: str = "trace_id",
        sample_rate_field: str = "sample_rate",
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.default_sample_rate = sample_rate
        self.request_id_field = request_id_field
        self.trace_id_field = trace_id_field
        self.sample_rate_field = sample_rate_field

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, self.request_id_field, None)
        if request_id:
            log_record[self.request_id_field] = request_id
        trace_id = getattr(record, self.trace_id_field, None)
        if trace_id:
            log_record[self.trace_id_field] = trace_id
        sample_rate = getattr(record, self.sample_rate_field, None)
        if sample_rate is None:
            sample_rate = self.default_sample_rate
        if sample_rate is not None:
            log_record[self.sample_rate_field] = sample_rate
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


def _normalise_config(config: dict[str, Any]) -> None:
    """Resolve dotted paths pointing to Watcher logging helpers."""

    def _replace(component: dict[str, Any], target: type[object]) -> None:
        for key in ("()", "class"):
            if _matches_target(component.get(key), target):
                component["()"] = target
                if key != "()":
                    component.pop(key, None)
                break

    formatters = config.get("formatters")
    if isinstance(formatters, dict):
        for formatter_config in formatters.values():
            if isinstance(formatter_config, dict):
                _replace(formatter_config, JSONFormatter)

    filters = config.get("filters")
    if isinstance(filters, dict):
        for filter_config in filters.values():
            if not isinstance(filter_config, dict):
                continue
            _replace(filter_config, RequestIdFilter)
            _replace(filter_config, SamplingFilter)


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
        _normalise_config(config)
        _apply_sample_rate(config, sample_rate)
        logging.config.dictConfig(config)
        _set_formatter_sample_rate(sample_rate)
        return

    if yaml:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        _normalise_config(config)
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
                "request_id_field": "request_id",
                "trace_id_field": "trace_id",
                "sample_rate_field": "sample_rate",
                "sample_rate": 1.0,
            }
        },
        "filters": {
            "request_id": {
                "()": "app.core.logging_setup.RequestIdFilter",
                "request_id_field": "request_id",
                "trace_id_field": "trace_id",
                "sample_rate_field": "sample_rate",
            },
            "sampling": {
                "()": "app.core.logging_setup.SamplingFilter",
                "sample_rate": 1.0,
                "sample_rate_field": "sample_rate",
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
    _normalise_config(config)
    _apply_sample_rate(config, sample_rate)
    logging.config.dictConfig(config)
    _set_formatter_sample_rate(sample_rate)


def configure(*, sample_rate: float | None = None) -> None:
    """Configure logging from the YAML configuration file if possible."""

    fallback_level: int | str | None = logging.INFO
    settings = None

    try:
        from config import get_settings
    except ImportError as exc:  # pragma: no cover - import cycle guard
        if getattr(exc, "name", None) not in {"config", "get_settings"}:
            raise
    else:
        settings = get_settings()
        fallback_level = getattr(
            logging, settings.logging.fallback_level, logging.INFO
        )

    config_path = None
    if settings is not None:
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
