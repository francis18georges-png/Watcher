from pathlib import Path
import logging
import logging.config
import datetime
import json
import os
import importlib.resources as resources
from contextvars import ContextVar

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Logging filter to inject a request_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - simple
        record.request_id = request_id_ctx.get("")
        return True


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

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
        return json.dumps(log_record)


def set_request_id(request_id: str) -> None:
    """Set the request identifier for subsequent log records."""
    request_id_ctx.set(request_id)


def _configure_from_path(config_path: Path) -> None:
    """Load logging configuration from ``config_path`` if possible."""
    if yaml and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    elif config_path.exists():  # pragma: no cover - used when PyYAML missing
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": "app.core.logging_setup.JSONFormatter"}},
            "filters": {"request_id": {"()": "app.core.logging_setup.RequestIdFilter"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filters": ["request_id"],
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filters": ["request_id"],
                    "filename": "watcher.log",
                },
            },
            "root": {"level": "INFO", "handlers": ["console", "file"]},
        }
        logging.config.dictConfig(config)
    else:  # pragma: no cover - config file missing
        logging.basicConfig(level=logging.INFO)


def configure() -> None:
    """Configure logging from the YAML configuration file if possible."""
    env_path = os.environ.get("LOGGING_CONFIG_PATH")
    if env_path:
        _configure_from_path(Path(env_path))
        return

    resource = resources.files("config") / "logging.yml"
    try:
        with resources.as_file(resource) as config_path:
            _configure_from_path(config_path)
    except FileNotFoundError:  # pragma: no cover - config resource missing
        logging.basicConfig(level=logging.INFO)
