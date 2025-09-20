"""Utilities to execute lightweight but real benchmark scenarios."""

from __future__ import annotations

import argparse
import gc
import hashlib
import html
import json
import logging
import math
import statistics
import tempfile
import time
import tracemalloc
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Final, Iterable, Iterator, Sequence


@contextmanager
def _preserve_logging_state() -> Iterator[None]:
    """Temporarily save and restore the root logger configuration."""

    root_logger = logging.getLogger()
    previous_level = root_logger.level
    previous_handlers = list(root_logger.handlers)
    previous_filters = list(root_logger.filters)
    logger_states: dict[str, bool] = {}
    for name, existing in list(logging.root.manager.loggerDict.items()):
        if isinstance(existing, logging.Logger):
            logger_states[existing.name] = existing.disabled
    try:
        yield
    finally:
        root_logger.handlers[:] = previous_handlers
        root_logger.filters[:] = previous_filters
        root_logger.setLevel(previous_level)
        for name, disabled in logger_states.items():
            logger = logging.getLogger(name)
            logger.disabled = disabled


class Bench:
    """Benchmark helper used by the learner, UI components and CI."""

    _BADGE_FILE: Final[str] = "performance_badge.svg"
    _JSONL_FILE: Final[str] = "benchmarks.jsonl"
    _SUMMARY_FILE: Final[str] = "benchmarks-latest.json"
    _THRESHOLDS_FILE: Final[str] = "bench_thresholds.json"
    _DEFAULT_BADGE_COLOR: Final[str] = "brightgreen"
    _COLOR_ALIASES: Final[dict[str, str]] = {
        # Canonical colours taken from https://shields.io/docs/colors
        "brightgreen": "#4c1",
        "success": "#4c1",
        "important": "#fe7d37",
        "critical": "#e05d44",
        "informational": "#007ec6",
        "inactive": "#9f9f9f",
    }

    def __init__(self, badge_path: Path | None = None) -> None:
        self.badge_path = (
            Path(badge_path)
            if badge_path is not None
            else Path("metrics") / self._BADGE_FILE
        )
        self.metrics_dir = self.badge_path.parent
        self.jsonl_path = self.metrics_dir / self._JSONL_FILE
        self.summary_path = self.metrics_dir / self._SUMMARY_FILE
        self.thresholds_path = self.metrics_dir / self._THRESHOLDS_FILE

    # ------------------------------------------------------------------
    # Public API
    def run_variant(self, name: str) -> float:
        """Return a deterministic pseudo-random score for ``name``."""

        h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
        return (h % 1000) / 1000.0

    def run_benchmarks(
        self,
        *,
        scenario: str | None = None,
        samples: int = 5,
        warmup: int = 1,
        jsonl_path: Path | None = None,
        summary_path: Path | None = None,
        thresholds_path: Path | None = None,
    ) -> dict[str, Any]:
        """Execute benchmark scenarios and persist aggregated metrics."""

        if samples <= 0:
            raise ValueError("samples must be a positive integer")
        if warmup < 0:
            raise ValueError("warmup must be >= 0")

        with _preserve_logging_state():
            scenario_map = self._build_scenarios()
            if scenario is not None:
                if scenario not in scenario_map:
                    raise KeyError(f"unknown benchmark scenario: {scenario}")
                selected = [(scenario, scenario_map[scenario])]
            else:
                selected = list(scenario_map.items())

            run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")
            thresholds = self._load_thresholds(thresholds_path)
            results: list[dict[str, Any]] = []

            for name, func in selected:
                durations, peaks = self._sample_scenario(
                    func, samples=samples, warmup=warmup
                )
                metrics = self._format_metrics(durations, peaks)
                status, breaches = self._evaluate_against_thresholds(
                    metrics, thresholds.get(name)
                )
                record: dict[str, Any] = {
                    "run_id": run_id,
                    "scenario": name,
                    "samples": samples,
                    "metrics": metrics,
                    "raw_samples": {
                        "durations_ms": [round(d * 1000.0, 6) for d in durations],
                        "memory_kb": [round(p / 1024.0, 6) for p in peaks],
                    },
                    "status": status,
                }
                if breaches:
                    record["breaches"] = breaches
                results.append(record)

            results.sort(key=lambda item: item["scenario"])
            summary = {
                "run_id": run_id,
                "generated_at": run_id,
                "results": results,
            }
            summary["overall_status"] = self._overall_status(results)

            jsonl_target = Path(jsonl_path) if jsonl_path is not None else self.jsonl_path
            summary_target = (
                Path(summary_path) if summary_path is not None else self.summary_path
            )
            jsonl_target.parent.mkdir(parents=True, exist_ok=True)
            summary_target.parent.mkdir(parents=True, exist_ok=True)
            self._write_jsonl(jsonl_target, results)
            self._write_summary(summary_target, summary)
            self._update_status_badge(summary)
        return summary

    def check_thresholds(
        self,
        *,
        summary_path: Path | None = None,
        thresholds_path: Path | None = None,
        update_badge: bool = False,
    ) -> list[str]:
        """Compare the latest benchmark metrics against predefined thresholds."""

        summary_file = Path(summary_path) if summary_path is not None else self.summary_path
        if not summary_file.exists():
            raise FileNotFoundError(f"summary file not found: {summary_file}")
        with _preserve_logging_state():
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            thresholds = self._load_thresholds(thresholds_path)

            overall, breaches = self._apply_thresholds(
                summary.get("results", []), thresholds
            )
            summary["overall_status"] = overall
            if breaches:
                summary["results"] = summary.get("results", [])
            self._write_summary(summary_file, summary)
            if update_badge:
                self._update_status_badge(summary)
        return breaches

    # ------------------------------------------------------------------
    # Scenario definitions
    def _build_scenarios(self) -> dict[str, Callable[[], None]]:
        return {
            "planner_briefing": self._scenario_planner_briefing,
            "learner_update": self._scenario_learner_update,
            "metrics_tracking": self._scenario_metrics_tracking,
            "memory_operations": self._scenario_memory_operations,
        }

    def _scenario_planner_briefing(self) -> None:
        from app.core.planner import Planner

        planner = Planner()
        base_inputs = ["analyse code", "lire documentation", "collecter feedback"]
        base_outputs = ["plan d'action", "rapports", "tests automatiques"]
        constraints = ["budget limite", "delai court", "code maintenable"]
        deliverables = ["README", "scripts", "pipeline CI"]
        success = [
            "tests verts",
            "documentation a jour",
            "deploiement sans regression",
        ]
        for i in range(15):
            planner.briefing(
                f"moderniser module {i}",
                inputs=base_inputs,
                outputs=base_outputs,
                constraints=constraints,
                deliverables=deliverables,
                success=success,
            )

    def _scenario_learner_update(self) -> None:
        from app.core.learner import Learner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = Learner(self, Path(tmpdir))
            state = [math.sin(i / 3.0) for i in range(1, 65)]
            rewards = [0.2, 0.6, -0.1, 1.0, 0.8, 0.4]
            for reward in rewards:
                learner.step(state, reward)
            learner.compare("variant_alpha", "variant_beta")

    def _scenario_metrics_tracking(self) -> None:
        from app.utils.metrics import PerformanceMetrics

        metrics = PerformanceMetrics()
        for size in range(200, 400, 40):
            with metrics.track_engine():
                sum((i * size) % 97 for i in range(2500))
        for size in range(100, 220, 30):
            with metrics.track_db():
                sorted((i * 3) % 17 for i in range(size))
        for size in range(60, 120, 20):
            with metrics.track_plugin():
                "".join(str(i) for i in range(size))
        if metrics.response_times:
            metrics.log_evaluation_score(statistics.fmean(metrics.response_times))
        metrics.log_error("synthetic benchmark error log")

    def _scenario_memory_operations(self) -> None:
        from app.core.memory import Memory

        with tempfile.TemporaryDirectory() as tmpdir:
            mem = Memory(Path(tmpdir) / "bench.db")
            prompts = [
                "réponse concise",
                "résumer article",
                "détailler plan",
                "trouver bug",
            ]
            answers = [
                "réponse générée",
                "résumé prêt",
                "plan détaillé",
                "correction appliquée",
            ]
            for index in range(64):
                prompt = prompts[index % len(prompts)]
                answer = answers[index % len(answers)]
                mem.add("chat_user", f"{prompt} #{index}")
                mem.add("chat_ai", f"{answer} #{index}")
            mem.summarize("chat_ai", max_items=20)
            for rating, prompt, answer in zip(
                [0.4, 0.7, 1.0], prompts, answers
            ):
                mem.add_feedback("chat", prompt, answer, rating)
            # Force iteration over the feedback generator to touch batching logic
            list(mem.iter_feedback(batch_size=2))
            # Execute a couple of similarity searches to exercise the vector index
            mem.search("plan détaillé", top_k=5)
            mem.search("résumé", top_k=5)

    # ------------------------------------------------------------------
    # Helpers
    def _sample_scenario(
        self, func: Callable[[], None], *, samples: int, warmup: int
    ) -> tuple[list[float], list[int]]:
        durations: list[float] = []
        peaks: list[int] = []
        total_runs = samples + warmup
        for iteration in range(total_runs):
            gc.collect()
            tracemalloc.start()
            start = time.perf_counter()
            try:
                func()
            finally:
                duration = time.perf_counter() - start
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            if iteration >= warmup:
                durations.append(duration)
                peaks.append(peak)
        return durations, peaks

    def _format_metrics(
        self, durations: Iterable[float], peaks: Iterable[int]
    ) -> dict[str, dict[str, float]]:
        duration_list = list(durations)
        peak_list = list(peaks)
        duration_stats = self._compute_stats(duration_list, scale=1000.0)
        memory_values = [p / 1024.0 for p in peak_list]
        memory_stats = self._compute_stats(memory_values, scale=1.0)
        return {
            "duration_ms": self._round_stats(duration_stats),
            "memory_kb": self._round_stats(memory_stats),
        }

    def _compute_stats(self, values: Iterable[float], *, scale: float) -> dict[str, float]:
        seq = list(values)
        if not seq:
            return {"mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        scaled = [v * scale for v in seq]
        scaled_sorted = sorted(scaled)
        return {
            "mean": statistics.fmean(scaled),
            "median": statistics.median(scaled_sorted),
            "p95": self._percentile(scaled_sorted, 0.95),
            "min": scaled_sorted[0],
            "max": scaled_sorted[-1],
        }

    def _round_stats(self, stats: dict[str, float], digits: int = 4) -> dict[str, float]:
        return {key: round(value, digits) for key, value in stats.items()}

    def _percentile(self, sorted_values: list[float], q: float) -> float:
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return sorted_values[0]
        position = max(0, min(len(sorted_values) - 1, math.ceil(q * len(sorted_values)) - 1))
        return sorted_values[position]

    def _load_thresholds(self, path: Path | None = None) -> dict[str, dict[str, float]]:
        thresholds_file = Path(path) if path is not None else self.thresholds_path
        if thresholds_file.exists():
            try:
                data = json.loads(thresholds_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {
                        name: value
                        for name, value in data.items()
                        if isinstance(value, dict)
                    }
            except json.JSONDecodeError:
                return {}
        return {}

    def _evaluate_against_thresholds(
        self,
        metrics: dict[str, dict[str, float]],
        threshold: dict[str, float] | None,
    ) -> tuple[str, list[str]]:
        if not threshold:
            return "unknown", []

        breaches: list[str] = []
        duration_stats = metrics.get("duration_ms", {})
        memory_stats = metrics.get("memory_kb", {})

        def _compare(limit_key: str, stats: dict[str, float], stat_key: str) -> None:
            limit = threshold.get(limit_key)
            if limit is None:
                return
            value = stats.get(stat_key)
            if value is None:
                return
            if value > float(limit):
                breaches.append(
                    f"{limit_key} exceeded: {value:.3f} > {float(limit):.3f}"
                )

        _compare("max_mean_ms", duration_stats, "mean")
        _compare("max_median_ms", duration_stats, "median")
        _compare("max_p95_ms", duration_stats, "p95")
        _compare("max_max_ms", duration_stats, "max")
        _compare("max_mean_kb", memory_stats, "mean")
        _compare("max_median_kb", memory_stats, "median")
        _compare("max_p95_kb", memory_stats, "p95")
        _compare("max_peak_kb", memory_stats, "max")

        return ("pass", []) if not breaches else ("fail", breaches)

    def _apply_thresholds(
        self,
        results: Iterable[dict[str, Any]],
        thresholds: dict[str, dict[str, float]],
    ) -> tuple[str, list[str]]:
        breaches: list[str] = []
        for result in results:
            scenario = result.get("scenario", "unknown")
            metrics = result.get("metrics", {})
            status, scenario_breaches = self._evaluate_against_thresholds(
                metrics, thresholds.get(scenario)
            )
            result["status"] = status
            if scenario_breaches:
                result["breaches"] = scenario_breaches
                breaches.extend(f"{scenario}: {msg}" for msg in scenario_breaches)
            else:
                result.pop("breaches", None)

        overall = self._overall_status(results)
        return overall, breaches

    def _overall_status(self, results: Iterable[dict[str, Any]]) -> str:
        statuses = [result.get("status", "unknown") for result in results]
        if statuses and all(status == "pass" for status in statuses):
            return "pass"
        if any(status == "fail" for status in statuses):
            return "fail"
        return "unknown"

    def _write_jsonl(self, path: Path, results: Iterable[dict[str, Any]]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            for result in results:
                fh.write(json.dumps(result, sort_keys=True))
                fh.write("\n")

    def _write_summary(self, path: Path, summary: dict[str, Any]) -> None:
        path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    def _update_status_badge(self, summary: dict[str, Any]) -> Path:
        status = summary.get("overall_status", "unknown")
        colour = {
            "pass": "brightgreen",
            "fail": "critical",
            "unknown": "informational",
        }.get(status, self._DEFAULT_BADGE_COLOR)
        return self._update_badge(status, label="bench", color=colour, fmt="{}")

    # ------------------------------------------------------------------
    # Badge helpers
    def _normalise_color(self, color: str) -> str:
        """Translate Shields.io colour keywords into valid SVG colours."""

        colour = color.strip()
        if not colour:
            return colour
        if colour.startswith("#"):
            return colour
        return self._COLOR_ALIASES.get(colour.lower(), colour)

    def _update_badge(
        self,
        value: float | str,
        *,
        label: str = "performance",
        color: str = _DEFAULT_BADGE_COLOR,
        fmt: str = "{:.0%}",
    ) -> Path:
        """Render and persist the badge representing ``value``."""

        if isinstance(value, str):
            right_text = value
        else:
            numeric = max(0.0, min(1.0, float(value)))
            try:
                right_text = fmt.format(numeric)
            except Exception:  # pragma: no cover - defensive fallback
                right_text = f"{numeric:.0%}"

        svg = self._render_svg_badge(label, right_text, color)
        self.badge_path.parent.mkdir(parents=True, exist_ok=True)
        self.badge_path.write_text(svg, encoding="utf-8")
        return self.badge_path

    def _render_svg_badge(self, label: str, message: str, color: str) -> str:
        """Create a tiny SVG badge similar to Shields.io output."""

        colour = self._normalise_color(color)
        safe_label = html.escape(label.strip())
        safe_message = html.escape(message.strip())

        def _text_width(text: str) -> int:
            # Roughly estimate the width used by the text using a monospace font
            # approximation (Shields uses a similar heuristic).  Enforce a
            # minimum width so very short texts still look balanced.
            return max(40, len(text) * 7 + 20)

        left_width = _text_width(safe_label)
        right_width = _text_width(safe_message)
        total_width = left_width + right_width
        label_x = left_width // 2
        value_x = left_width + right_width // 2

        return (
            "<svg xmlns=\"http://www.w3.org/2000/svg\" "
            f"width=\"{total_width}\" height=\"20\" role=\"img\" "
            f"aria-label=\"{safe_label}: {safe_message}\">\n"
            f"  <title>{safe_label}: {safe_message}</title>\n"
            f"  <rect width=\"{left_width}\" height=\"20\" fill=\"#555\"/>\n"
            f"  <rect x=\"{left_width}\" width=\"{right_width}\" height=\"20\" "
            f"fill=\"{colour}\"/>\n"
            "  <g fill=\"#fff\" text-anchor=\"middle\" "
            "font-family=\"Verdana,Geneva,DejaVu Sans,sans-serif\" "
            "font-size=\"11\">\n"
            f"    <text x=\"{label_x}\" y=\"14\">{safe_label}</text>\n"
            f"    <text x=\"{value_x}\" y=\"14\">{safe_message}</text>\n"
            "  </g>\n"
            "</svg>\n"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry-point used by automation and local developers."""

    bench = Bench()
    parser = argparse.ArgumentParser(description="Watcher micro benchmark runner")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute benchmark scenarios")
    run_parser.add_argument(
        "-s",
        "--scenario",
        choices=sorted(bench._build_scenarios().keys()),
        help="Run a single scenario (default: all)",
    )
    run_parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of samples collected for each scenario (default: 5)",
    )
    run_parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup iterations discarded before sampling",
    )
    run_parser.add_argument(
        "--jsonl",
        type=Path,
        help="Optional path to the JSONL file storing historical results",
    )
    run_parser.add_argument(
        "--summary",
        type=Path,
        help="Optional path to the JSON summary of the latest run",
    )
    run_parser.add_argument(
        "--thresholds",
        type=Path,
        help="Override the default threshold file",
    )

    check_parser = sub.add_parser("check", help="Validate benchmark results")
    check_parser.add_argument(
        "--summary",
        type=Path,
        help="Path to the summary file generated by the run command",
    )
    check_parser.add_argument(
        "--thresholds",
        type=Path,
        help="Override the default threshold file",
    )
    check_parser.add_argument(
        "--update-badge",
        action="store_true",
        help="Refresh the badge using the status from the summary file",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        summary = bench.run_benchmarks(
            scenario=args.scenario,
            samples=args.samples,
            warmup=args.warmup,
            jsonl_path=args.jsonl,
            summary_path=args.summary,
            thresholds_path=args.thresholds,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "check":
        breaches = bench.check_thresholds(
            summary_path=args.summary,
            thresholds_path=args.thresholds,
            update_badge=args.update_badge,
        )
        if breaches:
            for breach in breaches:
                print(breach)
            return 1
        print("All benchmark thresholds satisfied.")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    raise SystemExit(main())
