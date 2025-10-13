from __future__ import annotations

from copy import deepcopy
from importlib import resources
from pathlib import Path

import yaml

from app.core.first_run import FirstRunConfigurator


def _normalize_policy(data: dict) -> dict:
    normalized = deepcopy(data)
    subject = normalized.setdefault("subject", {})
    subject["hostname"] = "__HOST__"
    subject["generated_at"] = "__TIME__"

    windows = []
    for window in normalized.get("network_windows", []):
        windows.append(
            {
                "days": sorted(window.get("days", [])),
                "start": window.get("start"),
                "end": window.get("end"),
            }
        )
    normalized["network_windows"] = sorted(windows, key=lambda item: (item["start"], item["end"]))
    normalized["allowlist_domains"] = sorted(normalized.get("allowlist_domains", []))

    models = normalized.setdefault("models", {})
    for key in ("llm", "embedding"):
        section = models.setdefault(key, {})
        section.setdefault("license", "")
        section["name"] = section.get("name", "")
        section["sha256"] = section.get("sha256", "")
    return normalized


def test_policy_baseline_matches_first_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    baseline_text = resources.files("config").joinpath("policy.yaml").read_text(
        encoding="utf-8"
    )
    baseline_data = yaml.safe_load(baseline_text)

    generated_path = home / ".watcher" / "policy.yaml"
    generated_data = yaml.safe_load(generated_path.read_text(encoding="utf-8"))

    assert _normalize_policy(baseline_data) == _normalize_policy(generated_data)
