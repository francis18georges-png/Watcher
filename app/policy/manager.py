"""User-facing policy management helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from typing import Any, Iterable

import yaml

from .ledger import ConsentLedger, LedgerError
from .schema import DomainRule, Policy


class PolicyError(RuntimeError):
    """Raised when the policy file is missing or malformed."""


class PolicyManager:
    """High-level interface around ``policy.yaml`` and the consent ledger."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or Path.home()
        self.config_dir = self.home / ".watcher"
        self.policy_path = self.config_dir / "policy.yaml"
        self.ledger_path = self.config_dir / "consent-ledger.jsonl"

    def _read_policy(self) -> Policy:
        if not self.policy_path.exists():
            raise PolicyError("policy.yaml is missing – run 'watcher init --auto'")
        text = self.policy_path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise PolicyError("policy.yaml is not valid YAML") from exc
        normalised = self._normalise_policy_payload(data)
        return Policy.model_validate(normalised)

    def _normalise_policy_payload(self, data: Any) -> Any:
        """Upgrade legacy ``policy.yaml`` structures to the current schema."""

        if not isinstance(data, dict):
            return data

        payload = deepcopy(data)
        schema = Policy.model_json_schema()
        defaults_schema = (
            schema.get("$defs", {})
            .get("Defaults", {})
            .get("properties", {})
        )
        network_schema = (
            schema.get("$defs", {})
            .get("NetworkSection", {})
            .get("properties", {})
        )

        payload = self._normalise_defaults(payload, defaults_schema)
        payload = self._normalise_network(payload, network_schema)
        return payload

    def _normalise_defaults(
        self, payload: dict[str, Any], defaults_schema: dict[str, Any]
    ) -> dict[str, Any]:
        defaults = payload.get("defaults")
        if not isinstance(defaults, dict):
            return payload

        defaults = dict(defaults)
        expects_autostart = "autostart" in defaults_schema
        expects_corroboration = "require_corroboration" in defaults_schema

        if expects_autostart and "autostart" not in defaults:
            offline_value = defaults.pop("offline", None)
            default_value = defaults_schema.get("autostart", {}).get("default", False)
            if offline_value is None:
                autostart = default_value
            else:
                autostart = not bool(offline_value)
            defaults["autostart"] = autostart

        if expects_corroboration and "require_corroboration" not in defaults:
            consent_value = defaults.pop("require_consent", None)
            default_value = (
                defaults_schema.get("require_corroboration", {}).get("default", True)
            )
            if consent_value is None:
                corroboration = default_value
            else:
                corroboration = bool(consent_value)
            defaults["require_corroboration"] = corroboration

        allowed_keys = set(defaults_schema.keys())
        if allowed_keys:
            defaults = {key: defaults[key] for key in defaults if key in allowed_keys}

        payload["defaults"] = defaults
        return payload

    def _normalise_network(
        self, payload: dict[str, Any], network_schema: dict[str, Any]
    ) -> dict[str, Any]:
        network = payload.get("network")
        if not isinstance(network, dict):
            return payload

        network = dict(network)
        expects_windows = "windows" in network_schema
        expects_budgets = "budgets" in network_schema

        if expects_windows and "windows" not in network:
            allowed_windows = network.pop("allowed_windows", []) or []
            if not isinstance(allowed_windows, list):
                allowed_windows = []
            window_entry = {
                "name": "default",
                "cidrs": ["0.0.0.0/0", "::/0"],
                "allowed_windows": allowed_windows,
            }
            network["windows"] = [window_entry]

        if expects_budgets:
            budgets = network.get("budgets")
            if not isinstance(budgets, dict):
                budgets = {}
            for key in ("bandwidth_mb", "time_budget_minutes"):
                if key in network:
                    budgets[key] = network.pop(key)
            if budgets:
                network["budgets"] = budgets

        legacy_keys = {"allowed_windows", "bandwidth_mb", "time_budget_minutes"}
        for key in list(network):
            if key in legacy_keys and key not in network_schema:
                network.pop(key)

        payload["network"] = network
        return payload

    def _write_policy(self, policy: Policy) -> None:
        data = policy.to_dict()
        self.policy_path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )

    def _policy_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.policy_path.read_bytes())
        return digest.hexdigest()

    def show(self) -> str:
        """Return the policy file as a YAML string."""

        return self.policy_path.read_text(encoding="utf-8")

    def approve(
        self,
        *,
        domain: str,
        scope: str,
        categories: Iterable[str] | None = None,
        bandwidth_mb: int | None = None,
        time_budget_minutes: int | None = None,
    ) -> DomainRule:
        policy = self._read_policy()
        cats = list(categories or policy.categories.allowed)
        rule = DomainRule(
            domain=domain,
            scope=scope,
            categories=cats,
            bandwidth_mb=(
                bandwidth_mb if bandwidth_mb is not None else policy.network.bandwidth_mb
            ),
            time_budget_minutes=(
                time_budget_minutes
                if time_budget_minutes is not None
                else policy.network.time_budget_minutes
            ),
            last_approved=datetime.utcnow(),
        )
        policy.network.allowlist = [
            existing for existing in policy.network.allowlist if existing.domain != domain
        ]
        policy.network.allowlist.append(rule)
        self._write_policy(policy)
        self._record("approve", domain=domain, scope=scope)
        return rule

    def revoke(self, domain: str, scope: str | None = None) -> None:
        policy = self._read_policy()
        before = len(policy.network.allowlist)
        policy.network.allowlist = [
            existing
            for existing in policy.network.allowlist
            if existing.domain != domain or (scope and existing.scope != scope)
        ]
        if len(policy.network.allowlist) == before:
            raise PolicyError(f"aucune autorisation trouvée pour {domain}")
        self._write_policy(policy)
        self._record("revoke", domain=domain, scope=scope or "*")

    def _record(self, action: str, *, domain: str, scope: str) -> None:
        try:
            ledger = ConsentLedger(self.ledger_path)
        except LedgerError as exc:  # pragma: no cover - defensive
            raise PolicyError(str(exc)) from exc
        ledger.record(
            action=action,
            domain=domain,
            scope=scope,
            policy_hash=self._policy_hash(),
        )

