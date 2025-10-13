from __future__ import annotations

from pathlib import Path

import yaml

import pytest

from app.core.first_run import FirstRunConfigurator
from app.policy.manager import PolicyError, PolicyManager


def _load_policy(home: Path) -> dict:
    policy_path = home / ".watcher" / "policy.yaml"
    return yaml.safe_load(policy_path.read_text(encoding="utf-8"))


def test_policy_manager_approve_and_revoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    manager = PolicyManager(home=home)
    manager.approve(domain="example.com", scope="web")

    policy_data = _load_policy(home)
    assert "example.com" in policy_data["allowlist_domains"]

    ledger_lines = (
        (home / ".watcher" / "consents.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(ledger_lines) >= 2
    assert any('"action": "approve"' in line for line in ledger_lines[1:])

    manager.revoke("example.com")

    policy_data = _load_policy(home)
    assert "example.com" not in policy_data["allowlist_domains"]

    ledger_lines = (
        (home / ".watcher" / "consents.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert any('"action": "revoke"' in line for line in ledger_lines[1:])


def test_policy_manager_rejects_empty_domain(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    manager = PolicyManager(home=home)
    with pytest.raises(PolicyError):
        manager.approve(domain="  ", scope="web")


def test_policy_manager_detects_missing_entry_on_revoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    manager = PolicyManager(home=home)
    with pytest.raises(PolicyError):
        manager.revoke("unknown.test")
