from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import yaml

from pydantic import ValidationError

from .ledger import ConsentLedger, LedgerError
from .schema import Policy


class PolicyError(RuntimeError):
    """Raised when the policy file is missing or malformed."""


class PolicyManager:
    """High-level interface around ``policy.yaml`` and the consent ledger."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or Path.home()
        self.config_dir = self.home / ".watcher"
        self.policy_path = self.config_dir / "policy.yaml"
        self.ledger_path = self.config_dir / "consents.jsonl"
        legacy_ledger = self.config_dir / "consent-ledger.jsonl"
        if legacy_ledger.exists() and not self.ledger_path.exists():
            try:
                legacy_ledger.replace(self.ledger_path)
            except OSError:
                # If the rename fails continue using the legacy path to avoid
                # regressing behaviour for existing users.
                self.ledger_path = legacy_ledger

    def _read_policy(self) -> Policy:
        if not self.policy_path.exists():
            raise PolicyError("policy.yaml is missing – run 'watcher init --auto'")
        text = self.policy_path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise PolicyError("policy.yaml is not valid YAML") from exc

        try:
            return Policy.model_validate(data)
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
    ) -> str:
        del categories, bandwidth_mb, time_budget_minutes  # legacy compatibility
        policy = self._read_policy()
        domain_norm = domain.strip().lower()
        if not domain_norm:
            raise PolicyError("domain must not be empty")
        if domain_norm not in policy.allowlist_domains:
            policy.allowlist_domains.append(domain_norm)
            policy.allowlist_domains = sorted(set(policy.allowlist_domains))
            self._write_policy(policy)
        self._record("approve", domain=domain_norm, scope=scope)
        return domain_norm

    def revoke(self, domain: str, scope: str | None = None) -> None:
        policy = self._read_policy()
        domain_norm = domain.strip().lower()
        if not domain_norm:
            raise PolicyError("domain must not be empty")
        before = set(policy.allowlist_domains)
        policy.allowlist_domains = sorted(
            {item for item in policy.allowlist_domains if item != domain_norm}
        )
        if set(policy.allowlist_domains) == before:
            raise PolicyError(f"aucune autorisation trouvée pour {domain}")
        self._write_policy(policy)
        self._record("revoke", domain=domain_norm, scope=scope or "*")

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
