from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
import yaml

from pydantic import ValidationError

from .ledger import ConsentLedger, LedgerError
from .schema import DomainPolicyRule, Policy


class PolicyError(RuntimeError):
    """Raised when the policy file is missing or malformed."""


@dataclass(frozen=True, slots=True)
class PolicyApproval:
    """Result of an approval operation recorded in the policy ledger."""

    domain: str
    scope: str
    created: bool


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
            raise PolicyError(
                "policy.yaml is missing – run 'watcher init --fully-auto'"
            )
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
    ) -> PolicyApproval:
        policy = self._read_policy()
        rule = self._coerce_rule(domain=domain, scope=scope)
        created = policy.add_domain_rule(domain=rule.domain, scope=rule.scope)
        if created:
            self._write_policy(policy)
            self._record("approve", domain=rule.domain, scope=rule.scope)
        return PolicyApproval(domain=rule.domain, scope=rule.scope, created=created)

    def revoke(self, domain: str, scope: str | None = None) -> None:
        policy = self._read_policy()
        domain_norm = self._coerce_domain(domain)
        scope_norm = self._coerce_scope(scope) if scope is not None else None
        removed = policy.remove_domain_rule(domain=domain_norm, scope=scope_norm)
        if not removed:
            if scope_norm is None:
                raise PolicyError(f"aucune autorisation trouvée pour {domain_norm}")
            raise PolicyError(
                f"aucune autorisation trouvée pour {domain_norm} ({scope_norm})"
            )
        self._write_policy(policy)
        self._record("revoke", domain=domain_norm, scope=scope_norm or "*")

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

    @staticmethod
    def _coerce_rule(*, domain: str, scope: str) -> DomainPolicyRule:
        try:
            return DomainPolicyRule(domain=domain, scope=scope)
        except ValidationError as exc:
            raise PolicyError(_first_validation_message(exc)) from exc

    @classmethod
    def _coerce_domain(cls, domain: str) -> str:
        return cls._coerce_rule(domain=domain, scope="web").domain

    @staticmethod
    def _coerce_scope(scope: str) -> str:
        text = str(scope).strip().lower()
        if not text:
            raise PolicyError("scope must not be empty")
        if text not in {"web", "git"}:
            raise PolicyError("scope must be one of: web, git")
        return text


def _first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if errors:
        message = errors[0].get("msg")
        if isinstance(message, str):
            prefix = "Value error, "
            if message.startswith(prefix):
                return message[len(prefix) :]
            return message
    return str(exc)
