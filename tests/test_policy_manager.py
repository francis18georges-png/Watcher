from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.first_run import FirstRunConfigurator
from app.policy.manager import PolicyManager


def test_policy_manager_approve_and_revoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    configurator = FirstRunConfigurator(home=home)
    configurator.run(fully_auto=True, download_models=False)

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
    assert policy_data["autostart"] is False
    assert policy_data["defaults"]["offline_default"] is True
    assert policy_data["defaults"]["require_corroboration"] is True
    assert policy_data["defaults"]["kill_switch_file"].startswith(str(home / ".watcher"))
    windows = policy_data["network"]["network_windows"]
    assert windows and windows[0]["cidrs"] == ["0.0.0.0/0", "::/0"]
    assert windows[0]["windows"][0]["window"] == "09:00-18:00"

    allowlist = policy_data["network"]["allowlist"]
    assert any(entry["domain"] == "example.com" for entry in allowlist)

    ledger_lines = (
        (home / ".watcher" / "consent-ledger.jsonl").read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert len(ledger_lines) == 2
    assert '"action": "approve"' in ledger_lines[1]
    assert '"policy_version": 1' in ledger_lines[1]

    manager.revoke("example.com")

    policy_data = yaml.safe_load(
        (home / ".watcher" / "policy.yaml").read_text(encoding="utf-8")
    )
    assert not policy_data["network"]["allowlist"]


def test_policy_schema_requires_absolute_kill_switch() -> None:
    from pydantic import ValidationError

    policy = {
        "version": 1,
        "autostart": False,
        "subject": {
            "hostname": "test",
            "generated_at": "2024-01-01T00:00:00Z",
        },
        "defaults": {
            "offline_default": True,
            "require_consent": True,
            "require_corroboration": True,
            "kill_switch_file": "relative/path",
        },
        "network": {
            "network_windows": [
                {
                    "cidrs": ["0.0.0.0/0"],
                    "windows": [
                        {"days": ["mon"], "window": "00:00-23:59"},
                    ],
                }
            ],
            "allowlist": [],
            "budgets": {"bandwidth_mb": 1, "time_budget_minutes": 1},
        },
        "budgets": {"cpu_percent": 10, "ram_mb": 10},
        "categories": {"allowed": []},
        "models": {
            "llm": {"name": "x", "sha256": "a" * 64, "license": "MIT"},
            "embedding": {"name": "y", "sha256": "b" * 64, "license": "MIT"},
        },
    }

    from app.policy.schema import Policy

    with pytest.raises(ValidationError):
        Policy.model_validate(policy)


def test_policy_schema_rejects_invalid_cidr() -> None:
    from pydantic import ValidationError

    from app.policy.schema import Policy

    policy = {
        "version": 1,
        "autostart": False,
        "subject": {
            "hostname": "test",
            "generated_at": "2024-01-01T00:00:00Z",
        },
        "defaults": {
            "offline_default": True,
            "require_consent": True,
            "require_corroboration": True,
            "kill_switch_file": "/tmp/kill",
        },
        "network": {
            "network_windows": [
                {
                    "cidrs": ["invalid"],
                    "windows": [
                        {"days": ["mon"], "window": "00:00-23:59"},
                    ],
                }
            ],
            "allowlist": [],
            "budgets": {"bandwidth_mb": 1, "time_budget_minutes": 1},
        },
        "budgets": {"cpu_percent": 10, "ram_mb": 10},
        "categories": {"allowed": []},
        "models": {
            "llm": {"name": "x", "sha256": "a" * 64, "license": "MIT"},
            "embedding": {"name": "y", "sha256": "b" * 64, "license": "MIT"},
        },
    }

    with pytest.raises(ValidationError):
        Policy.model_validate(policy)
