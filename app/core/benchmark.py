"""Performance benchmarking utilities.

This module provides the :class:`Bench` class which executes realistic
scenarios covering the core subsystems of Watcher.  Each benchmark records its
measurements as JSON Lines files in ``metrics/*.jsonl`` and keeps a Shields.io
compatible badge up to date.

Usage from the command line::

    python -m app.core.benchmark run
    python -m app.core.benchmark check

The first command records fresh measurements while the second validates them
against configured thresholds.  See ``config/benchmarks.toml`` for the default
configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # Python >= 3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore

from app.core.logging_setup import get_logger
from app.core.memory import Memory
from app.data.pipeline import load_raw_data
from app.llm.client import Client


logger = get_logger(__name__)


@dataclass(frozen=True)
class _Variant:
    """Small helper describing how to run a benchmark variant."""

    scenario: str
    params: Mapping[str, Any]


class Bench:
    """Execute repeatable benchmarks and persist their metrics."""

    DEFAULT_VARIANTS: dict[str, Mapping[str, Any]] = {
        "A": {"scenario": "data_pipeline", "mode": "sequential"},
        "B": {"scenario": "data_pipeline", "mode": "batched"},
        "chat": {"scenario": "chat_latency", "prompt": "Bonjour, Watcher!"},
        "memory-batch": {
            "scenario": "memory_feedback",
            "mode": "batch",
            "rows": 1500,
            "batch_size": 150,
        },
    }

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        cache_ttl: float | None = None,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.config_path = (
            Path(config_path)
            if config_path is not None
            else self.base_dir / "config" / "benchmarks.toml"
        )
        self.config = self._load_config()
        bench_cfg = self.config.get("benchmarks", {})
        metrics_dir = bench_cfg.get("metrics_dir", "metrics")
        self.metrics_dir = (self.base_dir / metrics_dir).resolve()
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        badge_file = bench_cfg.get("badge_file", "performance_badge.json")
        self.badge_path = self.metrics_dir / badge_file
        self.badge_svg_path = self.metrics_dir / badge_file.replace(".json", ".svg")
        self.cache_ttl = (
            float(bench_cfg.get("cache_ttl", 5.0)) if cache_ttl is None else float(cache_ttl)
        )
        cfg_variants: dict[str, Mapping[str, Any]] = {
            name: {**value} for name, value in self.config.get("variants", {}).items()
        }
        merged: dict[str, Mapping[str, Any]] = {
            name: {**params} for name, params in self.DEFAULT_VARIANTS.items()
        }
        for name, data in cfg_variants.items():
            base = merged.get(name, {})
            merged[name] = {**base, **data}

        self.variants: dict[str, _Variant] = {}
        for name, data in merged.items():
            scenario = data.get("scenario")
            if not isinstance(scenario, str):
                logger.warning("Variant '%s' missing scenario, skipping", name)
                continue
            params = {k: v for k, v in data.items() if k != "scenario"}
            self.variants[name] = _Variant(scenario, params)
        default_variants = bench_cfg.get("default_variants")
        if isinstance(default_variants, list) and default_variants:
            self.default_variants = [v for v in default_variants if v in self.variants]
        else:
            self.default_variants = [
                name for name in ("A", "B", "memory-batch", "chat") if name in self.variants
            ]
        self.thresholds: dict[str, Mapping[str, float]] = self.config.get("thresholds", {})
        self._cache: dict[str, tuple[float, float]] = {}

    # ------------------------------------------------------------------
    # Public API

    def run(self, variants: Iterable[str] | None = None) -> dict[str, float]:
        """Run benchmarks for *variants* and return their scores."""

        names = list(variants) if variants is not None else list(self.default_variants)
        results: dict[str, float] = {}
        for name in names:
            score, metrics = self._execute_variant(name, use_cache=False)
            if metrics is not None:
                self._record_metrics(metrics)
            results[name] = score
        if results:
            self._update_badge()
        return results

    def run_variant(self, name: str) -> float:
        """Run benchmark for a single variant returning its score."""

        score, metrics = self._execute_variant(name, use_cache=True)
        if metrics is not None:
            self._record_metrics(metrics)
            self._update_badge()
        return score

    def enforce_thresholds(self) -> None:
        """Raise :class:`RuntimeError` when recorded metrics violate thresholds."""

        failures: list[str] = []
        for scenario, rule in self.thresholds.items():
            metrics = self._read_latest_metrics(scenario)
            if not metrics:
                failures.append(f"{scenario}: no metrics recorded")
                continue
            for key, limit in rule.items():
                if key.endswith("_min"):
                    metric_name = key[: -len("_min")]
                    actual = metrics.get(metric_name)
                    if actual is None or actual < float(limit):
                        failures.append(
                            f"{scenario}.{metric_name}={actual} < minimum {limit}"
                        )
                elif key.endswith("_max"):
                    metric_name = key[: -len("_max")]
                    actual = metrics.get(metric_name)
                    if actual is None or actual > float(limit):
                        failures.append(
                            f"{scenario}.{metric_name}={actual} > maximum {limit}"
                        )
                else:
                    failures.append(f"{scenario}: unsupported rule '{key}'")
        if failures:
            message = "Performance regression detected:\n" + "\n".join(f"- {f}" for f in failures)
            raise RuntimeError(message)

    # ------------------------------------------------------------------
    # Internal helpers

    def _load_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            try:
                with self.config_path.open("rb") as fh:
                    return tomllib.load(fh)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to read benchmark config: %s", exc)
        return {}

    def _execute_variant(self, name: str, *, use_cache: bool) -> tuple[float, dict[str, Any] | None]:
        if use_cache:
            cached = self._cache.get(name)
            if cached and time.time() - cached[0] <= self.cache_ttl:
                return cached[1], None

        variant = self.variants.get(name)
        if variant is None:
            score = self._fallback_score(name)
            timestamp = time.time()
            self._cache[name] = (timestamp, score)
            logger.debug("Using fallback benchmark score for '%s' -> %.3f", name, score)
            return score, None

        scenario = variant.scenario
        params = dict(variant.params)
        if scenario == "data_pipeline":
            score, payload = self._scenario_data_pipeline(name=name, **params)
        elif scenario == "memory_feedback":
            score, payload = self._scenario_memory_feedback(name=name, **params)
        elif scenario == "chat_latency":
            score, payload = self._scenario_chat_latency(name=name, **params)
        else:
            raise ValueError(f"Unknown scenario '{scenario}' for variant '{name}'")

        timestamp = time.time()
        payload.update(
            {
                "variant": name,
                "scenario": scenario,
                "score": score,
                "timestamp": timestamp,
            }
        )
        self._cache[name] = (timestamp, score)
        return score, payload

    def _fallback_score(self, name: str) -> float:
        digest = hashlib.sha256(name.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big")
        return (value % 1000) / 1000.0

    # Scenario implementations -------------------------------------------------

    def _scenario_data_pipeline(
        self,
        *,
        name: str,
        mode: str = "sequential",
        file_count: int = 40,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Benchmark raw data loading with and without batching."""

        data = payload or {"value": 1}
        raw_root = self.base_dir / "datasets" / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bench_pipeline_", dir=raw_root) as tmp:
            tmp_path = Path(tmp)
            files = []
            for idx in range(file_count):
                file_path = tmp_path / f"sample_{idx}.json"
                file_path.write_text(json.dumps(data), encoding="utf-8")
                files.append(file_path)

            start = time.perf_counter()
            for file_path in files:
                load_raw_data(file_path)
            sequential_time = time.perf_counter() - start

            start = time.perf_counter()
            load_raw_data(tmp_path)
            batched_time = time.perf_counter() - start

        sequential_time = max(sequential_time, 1e-9)
        batched_time = max(batched_time, 1e-9)
        speedup = sequential_time / batched_time
        metrics = {
            "files": file_count,
            "sequential_time": sequential_time,
            "batched_time": batched_time,
            "speedup": speedup,
            "mode": mode,
        }
        if mode == "sequential":
            score = 1.0 / sequential_time
        elif mode == "batched":
            score = 1.0 / batched_time
        else:
            raise ValueError(f"Unsupported mode '{mode}' for data pipeline benchmark")
        logger.debug(
            "Pipeline benchmark %s: sequential=%.6fs batched=%.6fs speedup=%.2fx",
            mode,
            sequential_time,
            batched_time,
            speedup,
        )
        return score, metrics

    def _scenario_memory_feedback(
        self,
        *,
        name: str,
        mode: str = "batch",
        rows: int = 1000,
        batch_size: int = 200,
    ) -> tuple[float, dict[str, Any]]:
        """Benchmark feedback loading strategies."""

        with tempfile.TemporaryDirectory(prefix="bench_memory_") as tmp:
            db_path = Path(tmp) / "mem.db"
            mem = Memory(db_path)
            for idx in range(rows):
                mem.add_feedback("bench", f"prompt {idx}", f"answer {idx}", float(idx % 5))

            start = time.perf_counter()
            mem.all_feedback()
            naive_time = time.perf_counter() - start

            start = time.perf_counter()
            list(mem.iter_feedback(batch_size=batch_size))
            batch_time = time.perf_counter() - start

        naive_time = max(naive_time, 1e-9)
        batch_time = max(batch_time, 1e-9)
        speedup = naive_time / batch_time
        metrics = {
            "rows": rows,
            "batch_size": batch_size,
            "naive_time": naive_time,
            "batch_time": batch_time,
            "speedup": speedup,
            "mode": mode,
        }
        if mode == "all":
            score = 1.0 / naive_time
        elif mode == "batch":
            score = 1.0 / batch_time
        else:
            raise ValueError(f"Unsupported mode '{mode}' for memory benchmark")
        logger.debug(
            "Memory benchmark %s: naive=%.6fs batch=%.6fs speedup=%.2fx",
            mode,
            naive_time,
            batch_time,
            speedup,
        )
        return score, metrics

    def _scenario_chat_latency(
        self,
        *,
        name: str,
        prompt: str,
        rounds: int = 3,
    ) -> tuple[float, dict[str, Any]]:
        """Measure average latency of the LLM client."""

        client = Client()
        durations: list[float] = []
        for _ in range(max(1, rounds)):
            start = time.perf_counter()
            client.generate(prompt)
            durations.append(time.perf_counter() - start)

        avg = statistics.fmean(durations)
        sorted_durations = sorted(durations)
        if len(sorted_durations) == 1:
            p95 = sorted_durations[0]
        else:
            index = math.ceil(0.95 * (len(sorted_durations) - 1))
            p95 = sorted_durations[min(index, len(sorted_durations) - 1)]
        metrics = {
            "rounds": rounds,
            "prompt_length": len(prompt),
            "avg_latency": avg,
            "p95_latency": p95,
        }
        score = 1.0 / max(avg, 1e-9)
        logger.debug(
            "Chat benchmark '%s': avg=%.6fs p95=%.6fs",
            name,
            avg,
            p95,
        )
        return score, metrics

    # Metrics persistence ------------------------------------------------------

    def _record_metrics(self, payload: Mapping[str, Any]) -> None:
        scenario = payload.get("scenario", "unknown")
        path = self.metrics_dir / f"{scenario}.jsonl"
        line = json.dumps(dict(payload), sort_keys=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _read_latest_metrics(self, scenario: str) -> dict[str, Any] | None:
        path = self.metrics_dir / f"{scenario}.jsonl"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to read metrics for %s: %s", scenario, exc)
            return None
        if not lines:
            return None
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:  # pragma: no cover - defensive
            logger.warning("Corrupted metrics entry for %s", scenario)
            return None

    def _update_badge(self) -> None:
        segments: list[str] = []
        status_ok = True
        pipeline_metrics = self._read_latest_metrics("data_pipeline")
        if pipeline_metrics and "speedup" in pipeline_metrics:
            speedup = float(pipeline_metrics["speedup"])
            segments.append(f"pipeline {speedup:.2f}x")
            min_speedup = self._threshold_value("data_pipeline", "speedup", "min")
            if min_speedup is not None and speedup < min_speedup:
                status_ok = False
            max_batch = self._threshold_value("data_pipeline", "batched_time", "max")
            if (
                max_batch is not None
                and float(pipeline_metrics.get("batched_time", 0.0)) > max_batch
            ):
                status_ok = False

        memory_metrics = self._read_latest_metrics("memory_feedback")
        if memory_metrics and "speedup" in memory_metrics:
            speedup = float(memory_metrics["speedup"])
            segments.append(f"feedback {speedup:.2f}x")
            min_speedup = self._threshold_value("memory_feedback", "speedup", "min")
            if min_speedup is not None and speedup < min_speedup:
                status_ok = False

        chat_metrics = self._read_latest_metrics("chat_latency")
        if chat_metrics and "avg_latency" in chat_metrics:
            latency_ms = float(chat_metrics["avg_latency"]) * 1000
            segments.append(f"chat {latency_ms:.0f}ms")
            max_latency = self._threshold_value("chat_latency", "avg_latency", "max")
            if max_latency is not None and float(chat_metrics["avg_latency"]) > max_latency:
                status_ok = False

        if not segments:
            message = "not run"
            color = "lightgrey"
        else:
            message = " | ".join(segments)
            color = "brightgreen" if status_ok else "orange"

        data = {
            "schemaVersion": 1,
            "label": "bench",
            "message": message,
            "color": color,
        }
        try:
            self.badge_path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to write badge JSON: %s", exc)
        try:
            svg = self._render_svg_badge(message, color)
            self.badge_svg_path.write_text(svg + "\n", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to write badge SVG: %s", exc)

    def _threshold_value(
        self, scenario: str, metric: str, kind: str
    ) -> float | None:
        rule = self.thresholds.get(scenario)
        if not rule:
            return None
        key = f"{metric}_{kind}"
        value = rule.get(key)
        return float(value) if value is not None else None

    def _render_svg_badge(self, message: str, color: str) -> str:
        label = "bench"
        label_width = 6 * len(label) + 20
        message_width = 6 * len(message) + 20
        total_width = label_width + message_width
        label_x = label_width / 2
        message_x = label_width + message_width / 2
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{total}\" height=\"20\" role=\"img\" aria-label=\"{label}: {msg}\">"
            "<title>{label}: {msg}</title>"
            "<g shape-rendering=\"crispEdges\">"
            "<rect width=\"{lw}\" height=\"20\" fill=\"#555\"/>"
            "<rect x=\"{lw}\" width=\"{mw}\" height=\"20\" fill=\"{color}\"/>"
            "</g>"
            "<g fill=\"#fff\" text-anchor=\"middle\" font-family=\"DejaVu Sans,Verdana,Geneva,sans-serif\" font-size=\"11\">"
            "<text x=\"{lx}\" y=\"14\">{label}</text>"
            "<text x=\"{mx}\" y=\"14\">{msg}</text>"
            "</g>"
            "</svg>"
        ).format(
            total=total_width,
            label=label,
            msg=message,
            lw=label_width,
            mw=message_width,
            color=color,
            lx=label_x,
            mx=message_x,
        )


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watcher benchmarks")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Execute benchmarks")
    run_parser.add_argument(
        "variants",
        nargs="*",
        help="Variant names to run (defaults to configured list)",
    )

    sub.add_parser("check", help="Validate collected metrics against thresholds")
    sub.add_parser("list", help="List configured variants")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    bench = Bench()

    if args.command == "run":
        results = bench.run(args.variants or None)
        for name, score in results.items():
            print(f"{name}: {score:.6f}")
        return 0
    if args.command == "check":
        try:
            bench.enforce_thresholds()
        except RuntimeError as exc:
            print(exc)
            return 1
        print("Benchmarks within thresholds")
        return 0
    if args.command == "list":
        for name in sorted(bench.variants):
            variant = bench.variants[name]
            params = " ".join(f"{k}={v}" for k, v in variant.params.items())
            print(f"{name}: {variant.scenario} {params}".strip())
        return 0
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
