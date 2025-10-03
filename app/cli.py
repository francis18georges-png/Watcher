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

    app_manifest = Path("app") / "plugins.toml"
    if app_manifest.is_file():
        return app_manifest

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

    mode_parser = sub.add_parser(
        "mode",
        help="Basculer le mode d'intelligence entre online et offline",
    )
    mode_parser.add_argument(
        "mode",
        choices=("offline", "online"),
        help="Mode cible: 'offline' désactive les appels réseaux, 'online' les réactive.",
    )

    run_parser = sub.add_parser(
        "run",
        help="Exécuter un scénario autonome minimal (offline par défaut)",
    )
    run_parser.add_argument(
        "--prompt",
        default="Présente Watcher en une phrase.",
        help="Invite utilisateur à exécuter.",
    )
    run_parser.add_argument(
        "--offline",
        action="store_true",
        help="Force le moteur en mode hors-ligne avant exécution.",
    )
    run_parser.add_argument(
        "--model",
        default=None,
        help="Nom du modèle local à utiliser (optionnel).",
    )

    args = parser.parse_args(argv)

    set_seed(args.seed)

    if args.command == "plugin" and args.plugin_command == "list":
        for plugin in _iter_plugins():
            print(plugin.name)
        return 0

    if args.command == "mode":
        target = str(args.mode).lower()
        offline = target == "offline"
        settings.intelligence.mode = "offline" if offline else "online"
        engine = Engine()
        engine.set_offline(offline)
        print(f"Mode intelligence défini sur {settings.intelligence.mode}")
        return 0

    if args.command == "run":
        engine = Engine()
        if args.offline or settings.intelligence.mode.lower() == "offline":
            engine.set_offline(True)
        if args.model:
            backend = getattr(engine.client, "backend", "llama.cpp")
            if backend == "llama.cpp":
                engine.client.model_path = Path(args.model)
                if hasattr(engine.client, "_llama_model"):
                    engine.client._llama_model = None  # type: ignore[attr-defined]
            else:
                engine.client.model = args.model
        answer = engine.chat(args.prompt)
        print(answer)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
