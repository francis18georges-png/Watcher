"""User-facing policy management helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from pydantic import ValidationError

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

        normalised = self._normalise_defaults(data)

        try:
            return Policy.model_validate(normalised)
        except ValidationError as exc:
            raise PolicyError("policy.yaml is invalid") from exc

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
            existing
            for existing in policy.network.allowlist
            if existing.domain != domain or existing.scope != scope
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

    def _normalise_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        defaults = data.get("defaults")
        if not isinstance(defaults, dict):
            return data

        legacy_aliases = {
            # ``consent_required`` and ``offline_mode`` were used in early
            # prototypes before the schema settled on ``require_consent`` and
            # ``offline``.  Preserve the value provided by the user instead of
            # discarding it.
            "consent_required": "require_consent",
            "offline_mode": "offline",
        }
        legacy_drop = {
            # ``auto_approve`` was removed in favour of the explicit
            # allowlist/ledger flow.
            "auto_approve",
        }

        cleaned_defaults: dict[str, Any] = {}
        for key, value in defaults.items():
            if key in legacy_drop:
                continue

            target = legacy_aliases.get(key, key)
            # If both the legacy alias and the new key are present, keep the
            # explicit modern key.
            if target in cleaned_defaults and target != key:
                continue

            cleaned_defaults[target] = value

        normalised = dict(data)
        normalised["defaults"] = cleaned_defaults
        return normalised

