"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from importlib.resources.abc import Traversable
from typing import Sequence

from config import get_settings
from app.tools import plugins

#: Manifest bundled with the :mod:`app` package.
_PLUGIN_MANIFEST: Traversable = plugins.DEFAULT_MANIFEST


def _iter_plugins() -> list[plugins.Plugin]:
    """Return all configured plugin instances."""

    return plugins.reload_plugins(_PLUGIN_MANIFEST)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the :mod:`watcher` command."""

    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="watcher",
        description=(
            "Watcher CLI (LLM backend: "
            f"{settings.llm.backend} / model: {settings.llm.model})"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plugin_parser = sub.add_parser("plugin", help="Plugin related commands")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command", required=True)
    plugin_sub.add_parser("list", help="List available plugins")

    args = parser.parse_args(argv)

    if args.command == "plugin" and args.plugin_command == "list":
        for plugin in _iter_plugins():
            print(plugin.name)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
