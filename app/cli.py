"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from importlib import resources
from pathlib import Path
from typing import Sequence

from config import get_settings
from app.core.engine import Engine
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


def _interactive_loop(engine: Engine) -> int:
    """Run an interactive chat session using *engine*."""

    print(f"[Watcher] Mode {'offline' if engine.is_offline else 'online'} activé")
    print(f"[Watcher] {engine.start_msg}")

    while True:
        try:
            prompt = input("[You] ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:  # pragma: no cover - manual interruption
            print()
            return 0

        lowered = prompt.lower()
        if lowered in {"exit", "quit"}:
            return 0
        if lowered.startswith("rate "):
            parts = lowered.split(maxsplit=1)
            try:
                score = float(parts[1])
            except (IndexError, ValueError):
                print("[Watcher] La note doit être comprise entre 0.0 et 1.0.")
                continue
            if not 0.0 <= score <= 1.0:
                print("[Watcher] La note doit être comprise entre 0.0 et 1.0.")
                continue
            print(f"[Watcher] {engine.add_feedback(score)}")
            continue
        if not prompt:
            continue
        answer = engine.chat(prompt)
        print(f"[Watcher] {answer}")


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

    run_parser = sub.add_parser("run", help="Lancer l'interface CLI")
    offline_group = run_parser.add_mutually_exclusive_group()
    offline_group.add_argument(
        "--offline",
        dest="offline",
        action="store_true",
        help="Forcer le mode offline (par défaut dans settings.toml).",
    )
    offline_group.add_argument(
        "--online",
        dest="offline",
        action="store_false",
        help="Autoriser les appels réseau/LLM lorsqu'ils sont disponibles.",
    )
    run_parser.set_defaults(offline=None)

    args = parser.parse_args(argv)

    set_seed(args.seed)

    if args.command == "plugin" and args.plugin_command == "list":
        for plugin in _iter_plugins():
            print(plugin.name)
        return 0

    if args.command == "run":
        engine = Engine()
        if args.offline is not None:
            engine.set_offline(args.offline)
        return _interactive_loop(engine)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
