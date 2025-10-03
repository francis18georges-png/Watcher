from __future__ import annotations

from pathlib import Path

import yaml

from app.core.first_run import FirstRunConfigurator
from app.policy.manager import PolicyManager


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
        (home / ".watcher" / "consent-ledger.jsonl").read_text(encoding="utf-8")
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
