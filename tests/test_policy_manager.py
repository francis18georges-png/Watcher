from __future__ import annotations
from pathlib import Path

import yaml

import pytest

from app.core.first_run import FirstRunConfigurator
from app.policy.manager import PolicyError, PolicyManager


def test_policy_manager_approve_and_revoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    manager = PolicyManager(home=home)
    manager.approve(
        domain="example.com",
        scope="web",
        categories=["documentation"],
        bandwidth_mb=64,
        time_budget_minutes=5,
    )

    policy_data = yaml.safe_load(
        (home / ".watcher" / "policy.yaml").read_text(encoding="utf-8")
    )
    allowlist = policy_data["network"]["allowlist"]
    assert any(entry["domain"] == "example.com" for entry in allowlist)

    ledger_lines = (
        (home / ".watcher" / "consents.jsonl").read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert len(ledger_lines) == 3
    assert '"action": "init"' in ledger_lines[1]
    assert '"action": "approve"' in ledger_lines[2]

    manager.revoke("example.com")

    policy_data = yaml.safe_load(
        (home / ".watcher" / "policy.yaml").read_text(encoding="utf-8")
    )
    assert not policy_data["network"]["allowlist"]


def test_policy_manager_multiple_scopes_same_domain(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    manager = PolicyManager(home=home)
    manager.approve(domain="example.com", scope="web")
    manager.approve(domain="example.com", scope="api")

    policy_data = yaml.safe_load(
        (home / ".watcher" / "policy.yaml").read_text(encoding="utf-8")
    )
    allowlist = policy_data["network"]["allowlist"]

    scopes = {entry["scope"] for entry in allowlist if entry["domain"] == "example.com"}
    assert scopes == {"web", "api"}


def test_read_policy_preserves_boolean_defaults(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    policy_path = home / ".watcher" / "policy.yaml"
    policy_data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    policy_data.setdefault("defaults", {})["offline"] = False
    policy_data["defaults"]["require_consent"] = False
    policy_path.write_text(
        yaml.safe_dump(policy_data, sort_keys=False),
        encoding="utf-8",
    )

    manager = PolicyManager(home=home)
    policy = manager._read_policy()

    assert policy.defaults.offline is False
    assert policy.defaults.require_consent is False


def test_read_policy_preserves_unknown_defaults_keys(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    policy_path = home / ".watcher" / "policy.yaml"
    policy_data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    policy_data.setdefault("defaults", {})["unexpected"] = "nope"
    policy_path.write_text(
        yaml.safe_dump(policy_data, sort_keys=False),
        encoding="utf-8",
    )

    manager = PolicyManager(home=home)

    with pytest.raises(PolicyError):
        manager._read_policy()
