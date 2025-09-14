"""Plugin protocol and discovery helpers."""

from __future__ import annotations

import importlib
import logging
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol

import tomllib


class Plugin(Protocol):
    """Simple plugin interface used by all Watcher extensions."""

    name: str

    def run(self) -> str:  # pragma: no cover - interface definition
        """Execute the plugin and return a human readable message."""
        ...


def load_entry_point_plugins(group: str = "watcher.plugins") -> list[Plugin]:
    """Return plugins discovered via :mod:`importlib.metadata` entry points."""

    plugins: list[Plugin] = []
    try:
        try:
            eps = entry_points(group=group)
        except TypeError:  # pragma: no cover - fallback for older Python
            eps = entry_points().get(group, [])  # type: ignore[assignment]
    except Exception:  # pragma: no cover - best effort
        logging.exception("Failed to query entry points")
        return plugins

    for ep in eps:
        try:
            cls = ep.load()
            plugin: Plugin = cls()
            plugins.append(plugin)
        except Exception:  # pragma: no cover - best effort
            logging.exception(
                "Failed to load entry point %s", getattr(ep, "name", "<unknown>")
            )
    return plugins


def reload_plugins(base: Path | None = None) -> list[Plugin]:
    """Load plugin instances defined in ``plugins.toml``.

    Parameters
    ----------
    base:
        Optional base directory containing the ``plugins.toml`` file.  When
        ``None`` the project root is used.
    """

    if base is None:
        base = Path(__file__).resolve().parents[2]

    cfg = base / "plugins.toml"
    plugins: list[Plugin] = []
    if cfg.exists():
        try:
            data = tomllib.loads(cfg.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - best effort
            logging.exception("Invalid plugins.toml")
        else:
            for item in data.get("plugins", []):
                path = item.get("path")
                if not path:
                    continue
                module_name, _, class_name = path.partition(":")
                try:
                    module = importlib.import_module(module_name)
                    cls = getattr(module, class_name)
                    plugin: Plugin = cls()
                    plugins.append(plugin)
                except Exception:  # pragma: no cover - best effort
                    logging.exception("Failed to load plugin %s", path)

    plugins.extend(load_entry_point_plugins())
    return plugins


__all__ = ["Plugin", "reload_plugins", "load_entry_point_plugins"]
