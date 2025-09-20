"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Sequence

from app.tools import plugins
from app.ui import main as ui_main

#: Base location containing the plugin manifest bundled with the :mod:`app` package.
_plugin_base: Traversable = resources.files("app")


def _iter_plugins() -> list[plugins.Plugin]:
    """Return all configured plugin instances."""

    return plugins.reload_plugins(_plugin_base)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the :mod:`watcher` command."""

    parser = argparse.ArgumentParser(prog="watcher", description="Watcher CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Lancer l'interface Watcher")
    run_parser.add_argument(
        "--offline",
        action="store_true",
        help="Démarrer avec le mode offline activé (aucun appel réseau/LLM).",
    )
    run_parser.add_argument(
        "--status-only",
        action="store_true",
        help="Afficher uniquement l'état sans lancer l'UI (mode test).",
    )

    plugin_parser = sub.add_parser("plugin", help="Plugin related commands")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command", required=True)
    plugin_sub.add_parser("list", help="List available plugins")

    args = parser.parse_args(argv)

    if args.command == "run":
        return ui_main.run_app(offline=args.offline, status_only=args.status_only)

    if args.command == "plugin" and args.plugin_command == "list":
        for plugin in _iter_plugins():
            print(plugin.name)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
