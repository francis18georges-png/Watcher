from __future__ import annotations

import json

from app.core.benchmark import Bench


def test_run_benchmarks_creates_artifacts(tmp_path) -> None:
    badge_path = tmp_path / "badge.svg"
    jsonl_path = tmp_path / "bench.jsonl"
    summary_path = tmp_path / "summary.json"
    bench = Bench(badge_path=badge_path)

    summary = bench.run_benchmarks(
        samples=1,
        warmup=0,
        jsonl_path=jsonl_path,
        summary_path=summary_path,
        thresholds_path=tmp_path / "thresholds.json",
    )

    assert jsonl_path.exists()
    lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == len(summary["results"])

    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_data["overall_status"] in {"pass", "fail", "unknown"}
    assert {result["scenario"] for result in summary_data["results"]}


def test_check_thresholds_detects_regressions(tmp_path) -> None:
    badge_path = tmp_path / "badge.svg"
    jsonl_path = tmp_path / "bench.jsonl"
    summary_path = tmp_path / "summary.json"
    thresholds_path = tmp_path / "thresholds.json"

    bench = Bench(badge_path=badge_path)
    summary = bench.run_benchmarks(
        samples=1,
        warmup=0,
        jsonl_path=jsonl_path,
        summary_path=summary_path,
        thresholds_path=thresholds_path,
    )

    scenario_name = summary["results"][0]["scenario"]
    thresholds_path.write_text(
        json.dumps({scenario_name: {"max_mean_ms": 0.0}}), encoding="utf-8"
    )

    breaches = bench.check_thresholds(
        summary_path=summary_path, thresholds_path=thresholds_path
    )

    assert breaches
    updated_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert updated_summary["overall_status"] == "fail"
