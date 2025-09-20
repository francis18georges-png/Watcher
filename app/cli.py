"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from importlib import resources
from pathlib import Path
from typing import Sequence

from config import get_settings
from app.core.reproducibility import set_seed
from app.tools import plugins


def _plugin_base() -> plugins.Location | None:
    """Return the preferred manifest location for plugin discovery."""

    manifest = Path("plugins.toml")
    if manifest.is_file():
        return manifest

    try:
        candidate = resources.files("app") / "plugins.toml"
    except ModuleNotFoundError:
        return None
    if candidate.is_file():
        return candidate
    return None


#: Manifest bundled with the :mod:`app` package.
_PLUGIN_MANIFEST: plugins.Location | None = _plugin_base()


def _iter_plugins() -> list[plugins.Plugin]:
    """Return all configured plugin instances."""

    return plugins.reload_plugins(_PLUGIN_MANIFEST)


def _run_watcher(offline: bool) -> int:
    """Start the Watcher application in the requested connectivity mode."""

    from app.ui.main import launch_app

    return launch_app(offline=offline)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the :mod:`watcher` command."""

    settings = get_settings()
    intelligence = getattr(settings, "intelligence", None)
    default_offline = False
    if intelligence is not None:
        default_offline = getattr(intelligence, "mode", "").lower() == "offline"
    parser = argparse.ArgumentParser(
        prog="watcher",
        description=(
            "Watcher CLI (LLM backend: "
            f"{settings.llm.backend} / model: {settings.llm.model})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=settings.training.seed,
        help=(
            "Graine aléatoire utilisée pour toutes les composantes stochastiques. "
            "Par défaut, celle définie dans config/settings.toml."
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    plugin_parser = sub.add_parser("plugin", help="Plugin related commands")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command", required=True)
    plugin_sub.add_parser("list", help="List available plugins")

    run_parser = sub.add_parser("run", help="Lancer l'interface Watcher")
    run_parser.add_argument(
        "--offline",
        dest="offline",
        action="store_true",
        help="Force le mode offline (désactive les appels réseau/LLM).",
    )
    run_parser.add_argument(
        "--online",
        dest="offline",
        action="store_false",
        help="Force explicitement le mode en ligne.",
    )
    run_parser.set_defaults(offline=default_offline)

    args = parser.parse_args(argv)

    set_seed(args.seed)

    if args.command == "run":
        return _run_watcher(args.offline)

    if args.command == "plugin" and args.plugin_command == "list":
        for plugin in _iter_plugins():
            print(plugin.name)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
