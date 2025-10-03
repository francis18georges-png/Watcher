"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from contextlib import suppress
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

from config import get_settings

from app.core.engine import Engine
from app.core.reproducibility import set_seed
from app.embeddings.store import SimpleVectorStore
from app.llm import rag
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

    ask_parser = sub.add_parser(
        "ask",
        help="Poser une question avec RAG local et obtenir une réponse déterministe",
    )
    ask_parser.add_argument("question", help="Question à poser à l'assistant.")
    ask_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Nombre de passages récupérés depuis la mémoire vectorielle.",
    )
    ask_parser.add_argument(
        "--namespace",
        default="default",
        help="Espace de noms de la base vectorielle locale à interroger.",
    )
    ask_parser.add_argument(
        "--offline",
        action="store_true",
        help="Force l'exécution hors-ligne avant la génération.",
    )

    ingest_parser = sub.add_parser(
        "ingest",
        help="Ingestion de fichiers locaux dans la mémoire vectorielle",
    )
    ingest_parser.add_argument(
        "sources",
        nargs="+",
        help="Fichiers ou dossiers contenant du texte à indexer.",
    )
    ingest_parser.add_argument(
        "--namespace",
        default="default",
        help="Espace de noms cible dans la base vectorielle.",
    )
    ingest_parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        default=None,
        help="Patron glob à utiliser lors de l'exploration récursive (par défaut: *.md, *.txt).",
    )
    ingest_parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Nombre maximum de documents traités par lot.",
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

    if args.command == "ask":
        if args.top_k < 1:
            parser.error("--top-k doit être un entier strictement positif")
        engine = Engine()
        offline = args.offline or settings.intelligence.mode.lower() == "offline"
        if offline:
            engine.set_offline(True)
        store = SimpleVectorStore(namespace=args.namespace)
        answer = rag.answer_question(
            args.question,
            k=args.top_k,
            client=engine.client,
            store=store,
        )
        print(answer)
        return 0

    if args.command == "ingest":
        if args.batch_size < 1:
            parser.error("--batch-size doit être >= 1")
        patterns = args.patterns or ["*.md", "*.txt"]
        sources = [_resolve_source(Path(raw)) for raw in args.sources]
        store = SimpleVectorStore(namespace=args.namespace)
        total = 0
        batch_texts: list[str] = []
        batch_meta: list[dict[str, str]] = []
        for file in _iter_source_files(sources, patterns):
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = file.read_text(encoding="utf-8", errors="ignore")
            text = text.strip()
            if not text:
                continue
            batch_texts.append(text)
            batch_meta.append({"path": str(file)})
            total += 1
            if len(batch_texts) >= args.batch_size:
                store.add(batch_texts, batch_meta)
                batch_texts.clear()
                batch_meta.clear()
        if batch_texts:
            store.add(batch_texts, batch_meta)
        print(
            f"Ingestion terminée: {total} document(s) indexé(s) dans le namespace '{args.namespace}'."
        )
        return 0

    parser.error("unknown command")
    return 2


def _resolve_source(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Source introuvable: {path}")
    return resolved


def _iter_source_files(paths: Iterable[Path], patterns: Sequence[str]) -> Iterable[Path]:
    for base in paths:
        if base.is_file():
            yield base
            continue
        if base.is_dir():
            for pattern in patterns:
                for candidate in base.rglob(pattern):
                    if candidate.is_file():
                        yield candidate
            continue
        with suppress(FileNotFoundError):
            resolved = base.resolve()
            if resolved.is_file():
                yield resolved


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
