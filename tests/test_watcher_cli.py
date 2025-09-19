"""Integration tests for the unified watcher CLI."""

from __future__ import annotations

import json
from pathlib import Path

from app import cli
from app.data import pipeline


def test_plugin_list_outputs_known_plugin(capsys):
    code = cli.main(["plugin", "list"])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert "hello" in out


def test_plugin_run_returns_json(capsys):
    code = cli.main(["plugin", "run", "--name", "hello"])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    payload = json.loads(out[0])
    assert payload["name"] == "hello"
    assert "Hello" in payload["result"]


def test_run_cli_prompt(monkeypatch, capsys):
    # Avoid binding the metrics port during tests.
    code = cli.main(
        [
            "run",
            "--mode",
            "cli",
            "--no-metrics",
            "--prompt",
            "Bonjour",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if not line.startswith("{")]
    assert any(line.startswith("[Watcher]") for line in lines)
    assert any(line for line in lines if not line.startswith("[Watcher]"))


def test_data_pipeline_creates_output(tmp_path: Path, monkeypatch, capsys):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    processed_dir = tmp_path / "processed"
    sample = {"message": "  salut  ", "values": [1, 1, 2, 1000]}
    (raw_dir / "sample.json").write_text(json.dumps(sample), encoding="utf-8")

    monkeypatch.setattr(pipeline, "RAW_DIR", raw_dir)
    monkeypatch.setattr(pipeline, "PROCESSED_DIR", processed_dir)

    code = cli.main(
        [
            "data",
            "pipeline",
            "--source",
            "sample.json",
            "--output",
            "result.json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert "result.json" in out

    output_path = processed_dir / "result.json"
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["message"] == "salut"
    assert saved["values"] == [1, 2]
