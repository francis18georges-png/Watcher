"""Command line interface for Watcher."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import textwrap
from contextlib import suppress
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

try:  # Python 3.11+
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib  # type: ignore[import-not-found]

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

DEFAULT_MODEL = {
    "name": "demo-smollm-135m-instruct",
    "filename": "demo-smollm-135m-instruct.Q4_K_M.gguf",
    "url": (
        "https://huggingface.co/QuantFactory/SmolLM-135M-Instruct-GGUF/resolve/main/"
        "SmolLM-135M-Instruct-Q4_K_M.gguf"
    ),
    "sha256": "43d2819fb6bb94f514f4f099263b4526a65293fee7fdcbec8d3f12df0d48529f",
    "size": 1_048_576,
}

WATCHER_HOME = Path.home() / ".watcher"
CONFIG_FILENAME = "config.toml"
POLICY_FILENAME = "policy.yaml"


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


def _verify_file(
    path: Path, expected_hash: str | None, expected_size: int | None
) -> bool:
    """Return ``True`` if ``path`` matches the provided size and digest."""

    if expected_hash is None:
        return False
    if not path.is_file():
        return False
    actual_size = path.stat().st_size
    if expected_size is not None and actual_size != int(expected_size):
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest.lower() == expected_hash.lower()


def _stage_default_model(target: Path) -> Path:
    """Copy the bundled demonstration model to ``target`` if needed."""

    target.parent.mkdir(parents=True, exist_ok=True)

    if _verify_file(target, DEFAULT_MODEL["sha256"], DEFAULT_MODEL["size"]):
        return target

    with resources.as_file(
        resources.files("app.assets.models") / DEFAULT_MODEL["filename"]
    ) as source_path:
        data = source_path.read_bytes()

    digest = hashlib.sha256(data).hexdigest()
    if digest != DEFAULT_MODEL["sha256"]:
        msg = "Le modèle embarqué ne correspond pas à la somme de contrôle attendue."
        raise RuntimeError(msg)

    target.write_bytes(data)
    return target


def perform_auto_init() -> int:
    """Initialise the user configuration directory without interaction."""

    configurator = FirstRunConfigurator()
    config_path = configurator.run(fully_auto=True, download_models=True)
    policy_path = configurator.policy_path
    ledger_path = configurator.consent_ledger

    config_data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    llm_section = config_data.get("model") or config_data.get("llm", {})

    model_path_str = (
        llm_section.get("path")
        or llm_section.get("model_path")
        or llm_section.get("model")
        or ""
    )
    model_path = Path(model_path_str).expanduser()
    expected_hash = (
        llm_section.get("sha256")
        or llm_section.get("model_sha256")
        or llm_section.get("sha")
    )

    actual_size: int | None = None
    if model_path.is_file():
        try:
            actual_size = model_path.stat().st_size
        except OSError:
            actual_size = None

    print(f"Configuration écrite dans {config_path}")
    print(f"Politique mise à jour dans {policy_path}")
    print(f"Journal des consentements initialisé dans {ledger_path}")
    if model_path_str:
        details = []
        if expected_hash:
            details.append(f"sha256={expected_hash}")
        if actual_size is not None:
            details.append(f"taille={actual_size}")
        suffix = f" ({', '.join(details)})" if details else ""
        print(f"Modèle prêt à l'emploi : {model_path}{suffix}")
    return 0


def perform_offline_run(prompt: str, model_name: str | None = None) -> int:
    """Execute a minimal offline inference using the packaged model."""

    config_path = WATCHER_HOME / CONFIG_FILENAME
    if not config_path.is_file():
        print(
            "Configuration introuvable. Exécutez `watcher init --fully-auto`.",
            file=sys.stderr,
        )
        return 1

    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    model_config = config.get("model") or {}
    llm_config = config.get("llm") or {}

    configured_name = model_config.get("name") or llm_config.get("name")
    configured_path = Path(
        model_config.get("path")
        or llm_config.get("model_path")
        or llm_config.get("path")
        or ""
    ).expanduser()
    expected_hash = (
        model_config.get("sha256")
        or llm_config.get("model_sha256")
        or llm_config.get("sha256")
    )
    expected_size = model_config.get("size") or llm_config.get("model_size")

    if not configured_name and configured_path.name:
        configured_name = configured_path.name

    if model_name and model_name != configured_name:
        print(
            f"Le modèle '{model_name}' n'est pas configuré (actuel: '{configured_name}').",
            file=sys.stderr,
        )
        return 1

    if not _verify_file(configured_path, expected_hash, expected_size):
        if expected_hash == DEFAULT_MODEL["sha256"]:
            with suppress(RuntimeError):
                _stage_default_model(configured_path)
        if not _verify_file(configured_path, expected_hash, expected_size):
            print(
                "Le modèle configuré est absent ou corrompu. "
                "Relancez `watcher init --fully-auto`.",
                file=sys.stderr,
            )
            return 1

    try:
        from llama_cpp import Llama
    except ImportError as exc:  # pragma: no cover - import side effect
        print(f"llama-cpp-python requis: {exc}", file=sys.stderr)
        return 1

    llm = Llama(
        model_path=str(configured_path),
        n_ctx=1024,
        n_threads=min(max(os.cpu_count() or 1, 1), 4),
        seed=42,
        verbose=False,
    )

    system_prompt = (
        "Tu es Watcher, un assistant local fonctionnant entièrement hors-ligne. "
        "Réponds brièvement et avec un ton professionnel."
    )
    completion = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
        temperature=0.1,
        stream=False,
    )

    message = ""
    if isinstance(completion, dict):
        choices = completion.get("choices") or []
        if choices:
            choice = choices[0]
            if isinstance(choice, dict):
                message = (
                    choice.get("message", {}).get("content")
                    or choice.get("text")
                    or ""
                )

    text = message.strip() or "Impossible de générer une réponse."
    print(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the :mod:`watcher` command."""
    arg_list = list(argv if argv is not None else sys.argv[1:])

    if arg_list and arg_list[0] == "init" and (
        "--auto" in arg_list[1:] or "--fully-auto" in arg_list[1:]
    ):
        return perform_auto_init()

    if arg_list and arg_list[0] == "run":
        probe = argparse.ArgumentParser(add_help=False)
        probe.add_argument("--prompt", default="Présente Watcher en une phrase.")
        probe.add_argument("--offline", action="store_true")
        probe.add_argument("--model", default=None)
        known, _ = probe.parse_known_args(arg_list[1:])
        if known.offline:
            return perform_offline_run(known.prompt, model_name=known.model)

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
        "--fully-auto",
        dest="fully_auto",
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
        path = configurator.run(fully_auto=args.fully_auto, download_models=True)
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
    manager = PolicyManager()
    try:
        policy = manager._read_policy()
        min_sources = max(2, policy.require_corroboration)
    except PolicyError:
        min_sources = 2
    return IngestPipeline(store, min_sources=min_sources)


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
