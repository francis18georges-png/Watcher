"""Command line entry point for Watcher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app import __version__
from app.core.benchmark import Bench
from app.data import pipeline
from app.tools import plugins


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watcher",
        description="Watcher developer assistant command line interface.",
    )
    parser.add_argument("--version", action="version", version=f"Watcher {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    run_parser = subparsers.add_parser("run", help="Launch the user interface")
    run_parser.add_argument(
        "--mode",
        choices=("auto", "gui", "cli"),
        default="auto",
        help="Interface mode: auto-detect, force GUI or force CLI.",
    )
    run_parser.add_argument(
        "--metrics-port",
        type=int,
        default=8000,
        help="Port used by the embedded metrics HTTP server.",
    )
    run_parser.add_argument(
        "--no-metrics",
        action="store_true",
        help="Disable the metrics HTTP server when running the UI.",
    )
    run_parser.add_argument(
        "--prompt",
        help="Prompt executed immediately when running in CLI mode.",
    )
    run_parser.set_defaults(func=_cmd_run)

    plugin_parser = subparsers.add_parser(
        "plugin", help="Inspect and execute Watcher plugins"
    )
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command")
    plugin_sub.required = True

    plugin_list = plugin_sub.add_parser("list", help="List available plugins")
    plugin_list.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Optional project root containing plugins.toml",
    )
    plugin_list.set_defaults(func=_cmd_plugin_list)

    plugin_run = plugin_sub.add_parser("run", help="Execute one or more plugins")
    plugin_run.add_argument(
        "--name",
        action="append",
        help="Name of the plugin to execute. Can be specified multiple times.",
    )
    plugin_run.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Optional project root containing plugins.toml",
    )
    plugin_run.set_defaults(func=_cmd_plugin_run)

    bench_parser = subparsers.add_parser(
        "bench", help="Run synthetic benchmark variants"
    )
    bench_parser.add_argument(
        "--variant",
        default="default",
        help="Benchmark variant name to execute.",
    )
    bench_parser.set_defaults(func=_cmd_bench)

    data_parser = subparsers.add_parser("data", help="Operate on datasets")
    data_sub = data_parser.add_subparsers(dest="data_command")
    data_sub.required = True

    pipeline_parser = data_sub.add_parser(
        "pipeline", help="Run the data cleaning pipeline"
    )
    pipeline_parser.add_argument(
        "--source",
        default=None,
        help="Optional JSON file relative to datasets/raw to process.",
    )
    pipeline_parser.add_argument(
        "--output",
        default="cleaned.json",
        help="Output filename stored in datasets/processed.",
    )
    pipeline_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the processed payload instead of writing files.",
    )
    pipeline_parser.set_defaults(func=_cmd_data_pipeline)

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    from app.ui import main as ui_main

    return ui_main.launch(
        mode=args.mode,
        metrics_port=args.metrics_port,
        enable_metrics=not args.no_metrics,
        prompt=args.prompt,
    )


def _plugin_base(root: Path | None) -> Path:
    return (root or Path(__file__).resolve().parents[2]).resolve()


def _cmd_plugin_list(args: argparse.Namespace) -> int:
    available = plugins.reload_plugins(_plugin_base(args.root))
    if not available:
        print("no plugins found")
        return 0
    for plugin in available:
        print(plugin.name)
    return 0


def _cmd_plugin_run(args: argparse.Namespace) -> int:
    available = plugins.reload_plugins(_plugin_base(args.root))
    if args.name:
        requested = set(args.name)
        selected = [p for p in available if p.name in requested]
        missing = requested - {p.name for p in selected}
        if missing:
            raise SystemExit(f"unknown plugin(s): {', '.join(sorted(missing))}")
    else:
        selected = available

    if not selected:
        print("no plugins executed")
        return 0

    for plugin in selected:
        result = plugin.run()
        print(json.dumps({"name": plugin.name, "result": result}, ensure_ascii=False))
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    bench = Bench()
    score = bench.run_variant(args.variant)
    print(json.dumps({"variant": args.variant, "score": score}))
    return 0


def _cmd_data_pipeline(args: argparse.Namespace) -> int:
    raw = pipeline.load_raw_data(args.source)

    def _prepare(item: dict) -> dict:
        return pipeline.clean_data(pipeline.normalize_data(item))

    if isinstance(raw, list):
        processed = [_prepare(item) for item in raw]
    elif isinstance(raw, dict):
        processed = _prepare(raw)
    else:  # pragma: no cover - defensive
        raise TypeError("expected dict or list of dicts from load_raw_data")

    result = pipeline.run_pipeline(processed)

    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    output = pipeline.transform_data(result, filename=args.output)
    if isinstance(output, list):
        for path in output:
            print(path)
    else:
        print(output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Watcher command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


__all__ = ["main"]
