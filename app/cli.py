"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from contextlib import suppress
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

from config import get_settings

from app.bootstrap import auto_configure_if_needed
from app.autopilot import (
    AutopilotController,
    AutopilotError,
    AutopilotRunResult,
    AutopilotScheduler,
)
from app.core.engine import Engine
from app.core.first_run import FirstRunConfigurator
from app.core.reproducibility import set_seed
from app.embeddings.store import SimpleVectorStore
from app.ingest import IngestPipeline, IngestValidationError, RawDocument
from app.llm import rag
from app.policy.manager import PolicyError, PolicyManager
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

    auto_configure_if_needed()
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

    init_parser = sub.add_parser(
        "init",
        help=(
            "Initialiser l'environnement utilisateur (~/.watcher) avec une"
            " configuration auto-générée."
        ),
    )
    init_parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Exécute l'initialisation sans interaction, détecte le matériel et"
            " télécharge les modèles déclarés."
        ),
    )

    policy_parser = sub.add_parser(
        "policy",
        help="Afficher ou modifier la politique de collecte et de scraping",
    )
    policy_sub = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("show", help="Afficher policy.yaml")
    approve_parser = policy_sub.add_parser(
        "approve",
        help="Accorder l'accès à un domaine dans la allowlist",
    )
    approve_parser.add_argument("--domain", required=True, help="Nom de domaine")
    approve_parser.add_argument(
        "--scope",
        default="web",
        help="Portée (ex: web, git)",
    )
    approve_parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        help="Catégories autorisées pour ce domaine",
    )
    approve_parser.add_argument(
        "--bandwidth",
        type=int,
        default=None,
        help="Budget bande passante en Mo",
    )
    approve_parser.add_argument(
        "--time-budget",
        type=int,
        default=None,
        help="Budget temps (minutes)",
    )

    revoke_parser = policy_sub.add_parser(
        "revoke",
        help="Révoquer un domaine préalablement approuvé",
    )
    revoke_parser.add_argument("--domain", required=True, help="Nom de domaine")
    revoke_parser.add_argument(
        "--scope",
        default=None,
        help="Portée à révoquer (par défaut toutes)",
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
    ingest_parser.add_argument(
        "--licence",
        default="CC-BY-4.0",
        help="Licence appliquée aux documents locaux (doit être compatible).",
    )
    ingest_parser.add_argument(
        "--min-sources",
        type=int,
        default=2,
        help=(
            "Nombre minimal de sources distinctes nécessaires pour valider une information."
        ),
    )

    autopilot_parser = sub.add_parser(
        "autopilot",
        help="Gérer le scheduler autopilot supervisé",
    )
    autopilot_sub = autopilot_parser.add_subparsers(
        dest="autopilot_command",
        required=True,
    )
    autopilot_enable = autopilot_sub.add_parser(
        "enable",
        help="Activer l'autopilot avec une liste de sujets",
    )
    autopilot_enable.add_argument(
        "--topics",
        required=True,
        help="Liste de sujets séparés par des virgules",
    )
    autopilot_disable = autopilot_sub.add_parser(
        "disable",
        help="Désactiver l'autopilot et vider éventuellement la file",
    )
    autopilot_disable.add_argument(
        "--topics",
        default=None,
        help="Sujets à retirer de la file avant désactivation (optionnel)",
    )
    autopilot_status = autopilot_sub.add_parser(
        "status",
        help="Afficher l'état courant de l'autopilot",
    )
    autopilot_status.add_argument(
        "--topics",
        default=None,
        help="Sujets à ajouter à la file temporairement pour inspection",
    )
    autopilot_run = autopilot_sub.add_parser(
        "run",
        help="Exécuter un cycle découverte → scraping → ingestion",
    )
    autopilot_run.add_argument(
        "--topics",
        default=None,
        help="Sujets supplémentaires (séparés par des virgules)",
    )
    autopilot_run.add_argument(
        "--noninteractive",
        action="store_true",
        help="Désactive la confirmation interactive avant l'exécution",
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

    if args.command == "init":
        configurator = FirstRunConfigurator()
        path = configurator.run(fully_auto=args.auto, download_models=True)
        print(f"Configuration utilisateur écrite dans {path}")
        return 0

    if args.command == "policy":
        manager = PolicyManager()
        try:
            if args.policy_command == "show":
                print(manager.show().rstrip())
                return 0
            if args.policy_command == "approve":
                rule = manager.approve(
                    domain=args.domain,
                    scope=args.scope,
                    categories=args.categories,
                    bandwidth_mb=args.bandwidth,
                    time_budget_minutes=args.time_budget,
                )
                print(
                    "Autorisation enregistrée pour "
                    f"{rule.domain} ({rule.scope})"
                )
                return 0
            if args.policy_command == "revoke":
                manager.revoke(args.domain, scope=args.scope)
                print(f"Autorisation révoquée pour {args.domain}")
                return 0
        except PolicyError as exc:
            parser.error(str(exc))

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
        if args.min_sources < 2:
            parser.error("--min-sources doit être >= 2")
        if args.batch_size < args.min_sources:
            parser.error("--batch-size doit être >= --min-sources")
        patterns = args.patterns or ["*.md", "*.txt"]
        sources = [_resolve_source(Path(raw)) for raw in args.sources]
        documents: list[RawDocument] = []
        for file in _iter_source_files(sources, patterns):
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = file.read_text(encoding="utf-8", errors="ignore")
            if not text.strip():
                continue
            try:
                timestamp = file.stat().st_mtime
            except OSError:
                timestamp = None
            published_at = (
                datetime.fromtimestamp(timestamp, tz=timezone.utc)
                if timestamp is not None
                else None
            )
            documents.append(
                RawDocument(
                    url=file.as_uri(),
                    title=file.stem,
                    text=text,
                    licence=args.licence,
                    published_at=published_at,
                )
            )
        if len(documents) < args.min_sources:
            parser.error(
                "Au moins deux sources distinctes sont requises pour l'ingestion."
            )
        store = SimpleVectorStore(namespace=args.namespace)
        pipeline = IngestPipeline(
            store,
            min_sources=args.min_sources,
        )
        seen_digests: set[str] = set()
        try:
            total = pipeline.ingest(documents, seen_digests=seen_digests)
        except IngestValidationError as exc:
            parser.error(str(exc))
        print(
            "Ingestion terminée: "
            f"{total} extrait(s) validé(s) dans le namespace '{args.namespace}'."
        )
        return 0

    if args.command == "autopilot":
        scheduler = AutopilotScheduler()
        engine = Engine()
        try:
            if args.autopilot_command == "enable":
                topics = _parse_topics(args.topics)
                if not topics:
                    parser.error("--topics doit contenir au moins un sujet")
                state = scheduler.enable(topics, engine=engine)
                message = (
                    "Autopilot activé (en ligne)."
                    if state.online
                    else _format_autopilot_wait_message(state)
                )
                print(f"{message} File: {_format_queue(state.queue)}")
                return 0
            if args.autopilot_command == "disable":
                topics = _parse_topics(args.topics) if args.topics else []
                state = scheduler.disable(topics or None, engine=engine)
                print(f"Autopilot désactivé. File: {_format_queue(state.queue)}")
                return 0
            if args.autopilot_command == "status":
                state = scheduler.evaluate(engine=engine)
                if state.online:
                    print(
                        f"Autopilot en ligne. File: {_format_queue(state.queue)}"
                    )
                else:
                    print(
                        f"Autopilot hors ligne ({state.last_reason or 'désactivé'}). "
                        f"File: {_format_queue(state.queue)}"
                    )
                if args.topics:
                    topics = _parse_topics(args.topics)
                    queue_topics = {entry.topic for entry in state.queue}
                    missing = [topic for topic in topics if topic not in queue_topics]
                    if missing:
                        print(
                            "Sujets absents de la file: " + ", ".join(missing)
                        )
                return 0
        except AutopilotError as exc:
            parser.error(str(exc))

        if args.autopilot_command == "run":
            topics = _parse_topics(args.topics)
            if not args.noninteractive and not _confirm_autopilot_run(topics):
                print("Cycle annulé par l'utilisateur.")
                return 1
            scheduler = AutopilotScheduler()
            pipeline = _build_autopilot_pipeline()
            crawler = _build_autopilot_crawler(noninteractive=args.noninteractive)
            controller = AutopilotController(
                scheduler=scheduler,
                pipeline=pipeline,
                crawler=crawler,
            )
            try:
                result = controller.run(topics or None)
            except AutopilotError as exc:
                parser.error(str(exc))
            for line in _summarise_autopilot_result(result):
                print(line)
            return 0 if result.reason is None else 3

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


def _parse_topics(raw: str | Sequence[str] | None) -> list[str]:
    if raw is None:
        return []
    parts: list[str]
    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = []
        for value in raw:
            parts.extend(str(value).split(","))
    topics: list[str] = []
    for item in parts:
        normalised = item.strip()
        if not normalised:
            continue
        if normalised not in topics:
            topics.append(normalised)
    return topics


def _format_queue(queue) -> str:
    if not queue:
        return "vide"
    labels: list[str] = []
    for entry in queue:
        topic = getattr(entry, "topic", None)
        if isinstance(topic, str) and topic:
            labels.append(topic)
        else:
            labels.append(str(entry))
    return ", ".join(labels) if labels else "vide"


def _format_autopilot_wait_message(state) -> str:
    reason = state.last_reason or "en attente"
    return f"Autopilot activé mais en attente ({reason})."


class _DefaultCrawler:
    """Fallback discovery crawler yielding no results."""

    def discover(self, topics: Sequence[str], rules: Sequence) -> Iterable:
        return []


def _confirm_autopilot_run(topics: Sequence[str]) -> bool:
    label = ", ".join(topics) if topics else "la file planifiée"
    answer = input(
        "L'exécution autopilot peut initier des requêtes réseau supervisées.\n"
        f"Confirmer le cycle pour {label} ? [o/N] "
    )
    return answer.strip().lower() in {"o", "oui", "y", "yes"}


def _build_autopilot_pipeline() -> IngestPipeline:
    store = SimpleVectorStore(namespace="autopilot")
    return IngestPipeline(store)


def _build_autopilot_crawler(*, noninteractive: bool) -> _DefaultCrawler:
    del noninteractive
    return _DefaultCrawler()


def _summarise_autopilot_result(result: AutopilotRunResult) -> list[str]:
    summary = (
        "Cycle autopilot terminé: "
        f"{result.ingested} source(s) ingérée(s), "
        f"{len(result.skipped)} ignorée(s), "
        f"{len(result.blocked)} bloquée(s)."
    )
    lines = [summary]
    if result.reason:
        lines.append(f"Cycle interrompu: {result.reason}")
    if result.skipped:
        lines.append("Ignorées: " + ", ".join(result.skipped))
    if result.blocked:
        lines.append("Bloquées: " + ", ".join(result.blocked))
    return lines
