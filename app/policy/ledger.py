"""Consent ledger handling."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path


class LedgerError(RuntimeError):
    """Raised when the consent ledger cannot be parsed."""


class ConsentLedger:
    """Append-only ledger storing user consent decisions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._metadata = self._read_metadata()
        secret_hex = self._metadata.get("secret_hex")
        if not isinstance(secret_hex, str):  # pragma: no cover - defensive
            raise LedgerError("ledger metadata missing secret_hex")
        self._secret = bytes.fromhex(secret_hex)

    def _read_metadata(self) -> dict[str, object]:
        if not self.path.exists():
            raise LedgerError("consent ledger not initialised")
        with self.path.open("r", encoding="utf-8") as fh:
            first_line = fh.readline().strip()
        try:
            data = json.loads(first_line)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise LedgerError("ledger metadata is invalid JSON") from exc
        if data.get("type") != "metadata":  # pragma: no cover - defensive
            raise LedgerError("ledger metadata missing type=metadata")
        return data

    @property
    def metadata(self) -> dict[str, object]:
        return dict(self._metadata)

    def record(
        self,
        *,
        action: str,
        domain: str,
        scope: str,
        policy_version: int,
        policy_hash: str,
    ) -> None:
        payload = {
            "type": "entry",
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "action": action,
            "domain": domain,
            "scope": scope,
            "policy_version": policy_version,
            "policy_hash": policy_hash,
        }
        message = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        signature = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        payload["signature"] = signature
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

