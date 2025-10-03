from __future__ import annotations

from pathlib import Path
from typing import Any

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


def test_read_policy_transforms_legacy_payload(tmp_path: Path, monkeypatch) -> None:
    legacy_policy = (
        Path(__file__).parent / "fixtures" / "policy_legacy.yaml"
    ).read_text(encoding="utf-8")

    home = tmp_path / "home"
    config_dir = home / ".watcher"
    config_dir.mkdir(parents=True)
    (config_dir / "policy.yaml").write_text(legacy_policy, encoding="utf-8")

    network_schema = {
        "properties": {
            "windows": {"type": "array"},
            "allowlist": {"type": "array"},
            "budgets": {"type": "object"},
        }
    }
    defaults_schema = {
        "properties": {
            "autostart": {"default": False, "type": "boolean"},
            "require_corroboration": {"default": True, "type": "boolean"},
            "kill_switch": {"default": False, "type": "boolean"},
        }
    }

    class FakePolicy:
        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:  # type: ignore[override]
            return {
                "$defs": {
                    "Defaults": defaults_schema,
                    "NetworkSection": network_schema,
                }
            }

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> dict[str, Any]:
            defaults = data["defaults"]
            assert "offline" not in defaults
            assert defaults["autostart"] is False
            assert defaults["require_corroboration"] is True

            network = data["network"]
            assert "allowed_windows" not in network
            assert "bandwidth_mb" not in network
            assert "time_budget_minutes" not in network
            assert network["budgets"] == {
                "bandwidth_mb": 128,
                "time_budget_minutes": 15,
            }
            assert network["windows"][0]["cidrs"] == ["0.0.0.0/0", "::/0"]
            assert network["windows"][0]["name"] == "default"
            assert network["windows"][0]["allowed_windows"]
            return data

    monkeypatch.setattr("app.policy.manager.Policy", FakePolicy)

    manager = PolicyManager(home=home)
    result = manager._read_policy()
    assert result["defaults"]["autostart"] is False
