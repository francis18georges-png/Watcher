"""Logging configuration setup for the Watcher application."""

from pathlib import Path
import logging
import logging.config

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None


def configure() -> None:
    """Configure logging from the YAML configuration file if possible."""
    config_path = Path(__file__).resolve().parents[2] / "config" / "logging.yml"
    if yaml and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:  # pragma: no cover - fallback when PyYAML not installed
        logging.basicConfig(level=logging.INFO)
