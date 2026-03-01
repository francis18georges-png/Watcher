from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import cli


@pytest.fixture(autouse=True)
def _stub_cli_settings(monkeypatch):
    settings = SimpleNamespace(
        llm=SimpleNamespace(backend="stub", model="stub-model"),
        training=SimpleNamespace(seed=42),
        intelligence=SimpleNamespace(mode="offline"),
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    return settings


def test_doctor_reports_errors_when_uninitialized(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli, "WATCHER_HOME", tmp_path / ".watcher")

    exit_code = cli.main(["doctor"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "Diagnostic Watcher: ERROR" in output
    assert "watcher_home" in output
    assert "config" in output


def test_doctor_json_ok_when_core_files_present(monkeypatch, tmp_path: Path, capsys) -> None:
    home = tmp_path / ".watcher"
    home.mkdir(parents=True)
    (home / "policy.yaml").write_text("version: 2\n", encoding="utf-8")
    (home / "consents.jsonl").write_text("{}\n", encoding="utf-8")
    (home / "reports").mkdir(parents=True)
    (home / "reports" / "weekly.html").write_text("<html></html>\n", encoding="utf-8")

    model_file = home / "model.gguf"
    model_file.write_bytes(b"abc")

    import hashlib

    digest = hashlib.sha256(b"abc").hexdigest()
    (home / "config.toml").write_text(
        "\n".join(
            [
                "[model]",
                f'path = "{model_file}"',
                f'sha256 = "{digest}"',
                "size = 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "WATCHER_HOME", home)

    exit_code = cli.main(["doctor", "--format", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    names = {item["name"]: item["status"] for item in payload["checks"]}
    assert names["config"] == "ok"
    assert names["policy"] == "ok"
    assert names["consent_ledger"] == "ok"
    assert names["model"] == "ok"


def test_doctor_export_bundle_redacts_config(monkeypatch, tmp_path: Path, capsys) -> None:
    home = tmp_path / ".watcher"
    home.mkdir(parents=True)
    model_file = home / "model.gguf"
    model_file.write_bytes(b"abc")

    import hashlib

    digest = hashlib.sha256(b"abc").hexdigest()
    (home / "config.toml").write_text(
        "\n".join(
            [
                "[model]",
                f'path = "{model_file}"',
                f'sha256 = "{digest}"',
                "size = 3",
                'source_url = "https://example.test/model.gguf"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (home / "policy.yaml").write_text("version: 2\n", encoding="utf-8")
    (home / "consents.jsonl").write_text("{}\n", encoding="utf-8")

    logs_dir = home / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "autopilot.jsonl").write_text('{"event": "ok"}\n', encoding="utf-8")

    monkeypatch.setattr(cli, "WATCHER_HOME", home)
    export = tmp_path / "diag.zip"

    exit_code = cli.main(["doctor", "--format", "json", "--export", str(export)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Bundle diagnostic généré:" in out
    assert export.is_file()

    with zipfile.ZipFile(export, "r") as bundle:
        names = set(bundle.namelist())
        assert "diagnostic.json" in names
        assert "config.toml" in names
        assert "policy.yaml" in names
        assert "consents.jsonl" in names
        assert "logs/autopilot.jsonl" in names
        config_data = bundle.read("config.toml").decode("utf-8")

    assert "<redacted>" in config_data
    assert str(model_file) not in config_data
